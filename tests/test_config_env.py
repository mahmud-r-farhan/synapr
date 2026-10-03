"""Unit tests for the environment-variable layer of the configuration system."""

import json
import os
from pathlib import Path

import pytest
from pydantic import ValidationError

from synapr.config import (
    ENV_VAR_SPECS,
    SECRET_MASK,
    SynaprConfig,
    coerce_env_value,
    default_config_path,
    discover_config_file,
    env_var_report,
    get_by_path,
    load_env_file,
    parse_env_text,
    redact_secret,
    render_env_example,
    set_by_path,
    write_env_file,
)

# --------------------------------------------------------------------------- registry


def test_every_env_spec_points_at_a_real_field() -> None:
    """The env registry must stay in sync with the pydantic models."""
    cfg = SynaprConfig()
    for spec in ENV_VAR_SPECS:
        get_by_path(cfg, spec.path)  # raises KeyError when the path disappears


def test_env_spec_names_are_unique() -> None:
    names = [name for spec in ENV_VAR_SPECS for name in spec.names]
    assert len(names) == len(set(names))


def test_env_spec_names_use_prefix_or_known_alias() -> None:
    for spec in ENV_VAR_SPECS:
        assert spec.name.startswith("SYNAPR_")


# --------------------------------------------------------------------------- coercion


@pytest.mark.parametrize(
    ("kind", "raw", "expected"),
    [
        ("str", " hello ", "hello"),
        ("int", "42", 42),
        ("float", "2.5", 2.5),
        ("bool", "true", True),
        ("bool", "OFF", False),
        ("csv", "a, b ,c", ["a", "b", "c"]),
        ("json", '{"a": "b"}', {"a": "b"}),
    ],
)
def test_coerce_env_value(kind: str, raw: str, expected: object) -> None:
    assert coerce_env_value(kind, raw) == expected


def test_coerce_env_value_rejects_garbage() -> None:
    with pytest.raises(ValueError):
        coerce_env_value("bool", "perhaps")
    with pytest.raises(ValueError):
        coerce_env_value("int", "x")


# --------------------------------------------------------------------------- overrides


def test_env_overrides_every_section(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SYNAPR_PROVIDER", "ollama")
    monkeypatch.setenv("SYNAPR_CRITIC_MODELS", "a:1, b:2")
    monkeypatch.setenv("SYNAPR_MAX_TOKENS", "256")
    monkeypatch.setenv("SYNAPR_AUTO_MERGE", "false")
    monkeypatch.setenv("SYNAPR_UI_PORT", "9000")
    monkeypatch.setenv("SYNAPR_EDITOR_OVERRIDES", '{"backend": "cursor"}')

    cfg = SynaprConfig.load()

    assert cfg.gateway.default_provider == "ollama"
    assert cfg.gateway.critic_models == ["a:1", "b:2"]
    assert cfg.gateway.max_tokens == 256
    assert cfg.pipeline.auto_merge is False
    assert cfg.ui.port == 9000
    assert cfg.editor.editor_overrides == {"backend": "cursor"}
    assert cfg.meta.env_overrides["gateway.default_provider"] == "SYNAPR_PROVIDER"


def test_env_overrides_take_precedence_over_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    config_file = tmp_path / "synapr.config.json"
    SynaprConfig(project_name="From File").save(config_file)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SYNAPR_PROJECT_NAME", "From Env")

    cfg = SynaprConfig.load()

    assert cfg.project_name == "From Env"
    assert cfg.meta.source_path == str(config_file.resolve())


def test_invalid_env_value_is_reported_not_fatal(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SYNAPR_MAX_TOKENS", "not-a-number")

    cfg = SynaprConfig.load()

    assert cfg.gateway.max_tokens == 4096
    assert any("SYNAPR_MAX_TOKENS" in error for error in cfg.meta.errors)


def test_unsetting_env_restores_previous_value(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SYNAPR_PLANNER_MODEL", "from-env")
    cfg = SynaprConfig.load()
    assert cfg.gateway.planner_model == "from-env"

    monkeypatch.delenv("SYNAPR_PLANNER_MODEL")
    cfg.apply_env()

    assert cfg.gateway.planner_model == "qwen2.5-coder:7b"
    assert "gateway.planner_model" not in cfg.meta.env_overrides


def test_openai_key_promotes_provider(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key-value")

    cfg = SynaprConfig.load()

    assert cfg.gateway.openai_api_key == "sk-test-key-value"
    assert cfg.gateway.default_provider == "openai"


def test_explicit_provider_wins_over_promotion(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key-value")
    monkeypatch.setenv("SYNAPR_PROVIDER", "ollama")

    assert SynaprConfig.load().gateway.default_provider == "ollama"


# --------------------------------------------------------------------------- dotenv


def test_parse_env_text_handles_quotes_exports_and_comments() -> None:
    parsed = parse_env_text(
        "\n".join(
            [
                "# comment",
                "export SYNAPR_PROVIDER='ollama'",
                'SYNAPR_PLANNER_MODEL="qwen2.5-coder:7b"',
                "EMPTY=",
                "not a pair",
            ]
        )
    )
    assert parsed["SYNAPR_PROVIDER"] == "ollama"
    assert parsed["SYNAPR_PLANNER_MODEL"] == "qwen2.5-coder:7b"
    assert parsed["EMPTY"] == ""
    assert "not a pair" not in parsed


def test_dotenv_file_is_loaded_by_config(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    (tmp_path / ".env").write_text("SYNAPR_PROVIDER=lmstudio\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    cfg = SynaprConfig.load()

    assert cfg.gateway.default_provider == "lmstudio"
    assert cfg.meta.env_file == str((tmp_path / ".env").resolve())


def test_real_environment_beats_dotenv(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    (tmp_path / ".env").write_text("SYNAPR_PROVIDER=lmstudio\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SYNAPR_PROVIDER", "vllm")

    assert SynaprConfig.load().gateway.default_provider == "vllm"


def test_write_env_file_updates_in_place(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("# header\nSYNAPR_PROVIDER=mock\nOTHER=keep\n", encoding="utf-8")

    write_env_file({"SYNAPR_PROVIDER": "ollama", "SYNAPR_UI_PORT": "9100"}, env_path)
    content = env_path.read_text(encoding="utf-8")

    assert "SYNAPR_PROVIDER=ollama" in content
    assert "OTHER=keep" in content
    assert "SYNAPR_UI_PORT=9100" in content
    assert "# header" in content
    assert content.count("SYNAPR_PROVIDER=") == 1


def test_write_env_file_removes_keys(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("SYNAPR_PROVIDER=ollama\nSYNAPR_UI_PORT=9100\n", encoding="utf-8")

    write_env_file({}, env_path, remove=["SYNAPR_PROVIDER"])

    content = env_path.read_text(encoding="utf-8")
    assert "SYNAPR_PROVIDER" not in content
    assert "SYNAPR_UI_PORT=9100" in content


def test_load_env_file_does_not_override_existing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("SYNAPR_PROVIDER=lmstudio\n", encoding="utf-8")
    monkeypatch.setenv("SYNAPR_PROVIDER", "groq")

    load_env_file(env_path)

    assert os.environ["SYNAPR_PROVIDER"] == "groq"


def test_load_env_file_missing_returns_empty(tmp_path: Path) -> None:
    assert load_env_file(tmp_path / "nope.env") == {}


# --------------------------------------------------------------------------- secrets


def test_redaction_keeps_last_four_characters() -> None:
    assert redact_secret(None) is None
    assert redact_secret("abc") == SECRET_MASK
    assert redact_secret("sk-super-secret-1234").endswith("1234")


def test_to_dict_redacts_secrets() -> None:
    cfg = SynaprConfig()
    cfg.gateway.openai_api_key = "sk-super-secret-1234"

    assert cfg.to_dict(redact=True)["gateway"]["openai_api_key"].startswith(SECRET_MASK)
    assert cfg.to_dict()["gateway"]["openai_api_key"] == "sk-super-secret-1234"
    assert cfg.secret_status()["gateway.openai_api_key"] is True


def test_apply_updates_ignores_masked_secret() -> None:
    cfg = SynaprConfig()
    cfg.gateway.openai_api_key = "sk-super-secret-1234"
    masked = cfg.to_dict(redact=True)

    updated = cfg.apply_updates({"gateway": {"openai_api_key": masked["gateway"]["openai_api_key"]}})

    assert updated.gateway.openai_api_key == "sk-super-secret-1234"


def test_apply_updates_can_clear_a_secret() -> None:
    cfg = SynaprConfig()
    cfg.gateway.openai_api_key = "sk-super-secret-1234"

    assert cfg.apply_updates({"gateway": {"openai_api_key": ""}}).gateway.openai_api_key is None


def test_apply_updates_validates() -> None:
    with pytest.raises(ValidationError):
        SynaprConfig().apply_updates({"gateway": {"temperature": 11}})


def test_apply_updates_is_a_deep_merge() -> None:
    cfg = SynaprConfig()
    updated = cfg.apply_updates({"gateway": {"planner_model": "x"}})

    assert updated.gateway.planner_model == "x"
    assert updated.gateway.arbiter_model == cfg.gateway.arbiter_model


# --------------------------------------------------------------------------- persistence


def test_env_sourced_values_are_not_persisted(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SYNAPR_PROVIDER", "groq")
    monkeypatch.setenv("SYNAPR_GROQ_API_KEY", "gsk_secret_value_123")

    cfg = SynaprConfig.load()
    cfg.project_name = "Persisted"
    target = cfg.save(tmp_path / "synapr.config.json")

    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["project_name"] == "Persisted"
    assert payload["gateway"]["default_provider"] == "mock"
    assert payload["gateway"]["groq_api_key"] is None


def test_save_is_atomic_and_creates_parents(tmp_path: Path) -> None:
    target = tmp_path / "nested" / "dir" / "synapr.config.json"
    SynaprConfig().save(target)

    assert target.is_file()
    assert not list(tmp_path.glob("**/.synapr-config-*"))


def test_save_hardens_permissions_for_secrets(tmp_path: Path) -> None:
    cfg = SynaprConfig()
    cfg.gateway.openai_api_key = "sk-secret-value-9999"
    target = cfg.save(tmp_path / "synapr.config.json")

    if os.name != "nt":
        assert oct(target.stat().st_mode)[-3:] == "600"


def test_corrupt_config_file_falls_back_to_defaults(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    (tmp_path / "synapr.config.json").write_text("{ not json", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    cfg = SynaprConfig.load()

    assert cfg.gateway.default_provider == "mock"
    assert cfg.meta.errors


def test_unknown_keys_in_file_are_ignored(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    (tmp_path / "synapr.config.json").write_text(
        json.dumps({"project_name": "Legacy", "legacy_section": {"x": 1}}), encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)

    cfg = SynaprConfig.load()

    assert cfg.project_name == "Legacy"
    assert not cfg.meta.errors


# --------------------------------------------------------------------------- helpers


def test_dotted_path_helpers() -> None:
    cfg = SynaprConfig()
    set_by_path(cfg, "gateway.planner_model", "model-x")

    assert get_by_path(cfg, "gateway.planner_model") == "model-x"
    with pytest.raises(KeyError):
        get_by_path(cfg, "gateway.nope")
    with pytest.raises(KeyError):
        set_by_path(cfg, "nope.nope", 1)


def test_set_by_path_validates() -> None:
    with pytest.raises(ValidationError):
        set_by_path(SynaprConfig(), "ui.port", 99999)


def test_discover_config_file(tmp_path: Path) -> None:
    assert discover_config_file(base_dir=tmp_path) is None
    target = default_config_path(tmp_path)
    SynaprConfig().save(target)
    assert discover_config_file(base_dir=tmp_path) == target


def test_env_var_report_marks_active_variables(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SYNAPR_PROVIDER", "ollama")
    report = {item["name"]: item for item in env_var_report(SynaprConfig.load(use_env=True))}

    assert report["SYNAPR_PROVIDER"]["is_set"] is True
    assert report["SYNAPR_PROVIDER"]["effective_value"] == "ollama"
    assert report["SYNAPR_UI_PORT"]["is_set"] is False


def test_env_report_never_leaks_secret_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SYNAPR_GROQ_API_KEY", "gsk_very_secret_value")
    report = {item["name"]: item for item in env_var_report(SynaprConfig.load(use_env=True))}

    assert report["SYNAPR_GROQ_API_KEY"]["effective_value"].startswith(SECRET_MASK)
    assert "very_secret" not in json.dumps(report)


def test_render_env_example_documents_every_variable() -> None:
    rendered = render_env_example()
    for spec in ENV_VAR_SPECS:
        assert spec.name in rendered


def test_gateway_helpers_resolve_urls_and_keys() -> None:
    cfg = SynaprConfig()
    cfg.gateway.groq_api_key = "gsk_abc"

    assert cfg.gateway.base_url_for("groq") == cfg.gateway.groq_base_url
    assert cfg.gateway.base_url_for("unknown") == cfg.gateway.openai_base_url
    assert cfg.gateway.api_key_for("groq") == "gsk_abc"
    assert cfg.gateway.api_key_for("vllm") == "not-needed"
    assert cfg.gateway.is_local_provider is True


def test_provider_values_are_normalised() -> None:
    assert SynaprConfig.model_validate(
        {"gateway": {"default_provider": "  OLLAMA "}}
    ).gateway.default_provider == "ollama"
