"""Unit tests for environment overrides and coercion."""

from pathlib import Path

import pytest

from synapr.config import ENV_VAR_SPECS, SynaprConfig, coerce_env_value, get_by_path


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
