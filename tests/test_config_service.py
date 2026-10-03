"""Unit tests for the runtime configuration service (visual configurator backend)."""

import json
from pathlib import Path

import pytest

from synapr.config import SECRET_MASK, SynaprConfig
from synapr.core.config_service import (
    ConfigService,
    ConfigServiceError,
    get_config_service,
    reset_config_service,
    set_config_service,
)


@pytest.fixture
def service(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> ConfigService:
    monkeypatch.chdir(tmp_path)
    return ConfigService(base_dir=tmp_path)


# --------------------------------------------------------------------------- lifecycle


def test_singleton_accessors(tmp_path: Path) -> None:
    reset_config_service()
    first = get_config_service()
    assert get_config_service() is first

    replacement = ConfigService(base_dir=tmp_path)
    assert set_config_service(replacement) is replacement
    assert get_config_service() is replacement

    reset_config_service()
    assert get_config_service() is not replacement


def test_update_applies_and_persists(service: ConfigService, tmp_path: Path) -> None:
    service.update({"gateway": {"planner_model": "deepseek-coder:6.7b"}}, persist=True)

    assert service.config.gateway.planner_model == "deepseek-coder:6.7b"
    payload = json.loads((tmp_path / "synapr.config.json").read_text(encoding="utf-8"))
    assert payload["gateway"]["planner_model"] == "deepseek-coder:6.7b"


def test_update_without_persist_leaves_disk_untouched(
    service: ConfigService, tmp_path: Path
) -> None:
    service.update({"project_name": "Memory Only"}, persist=False)

    assert service.config.project_name == "Memory Only"
    assert not (tmp_path / "synapr.config.json").exists()


def test_update_rejects_invalid_values(service: ConfigService) -> None:
    with pytest.raises(ConfigServiceError) as excinfo:
        service.update({"gateway": {"temperature": 42}})
    assert "temperature" in str(excinfo.value)


def test_update_rejects_non_mapping(service: ConfigService) -> None:
    with pytest.raises(ConfigServiceError):
        service.update(["not", "a", "dict"])  # type: ignore[arg-type]


def test_set_value_coerces_strings(service: ConfigService) -> None:
    service.set_value("ui.port", "9123", persist=False)
    service.set_value("pipeline.auto_merge", "false", persist=False)
    service.set_value("gateway.critic_models", "a,b", persist=False)

    assert service.config.ui.port == 9123
    assert service.config.pipeline.auto_merge is False
    assert service.config.gateway.critic_models == ["a", "b"]


def test_set_value_rejects_unknown_path(service: ConfigService) -> None:
    with pytest.raises(ConfigServiceError):
        service.set_value("gateway.does_not_exist", "x", persist=False)


def test_set_value_rejects_invalid_value(service: ConfigService) -> None:
    with pytest.raises(ConfigServiceError):
        service.set_value("ui.port", "70000", persist=False)


def test_reset_restores_defaults(service: ConfigService) -> None:
    service.update({"project_name": "Changed"}, persist=False)
    service.reset()

    assert service.config.project_name == SynaprConfig().project_name


def test_reload_rereads_disk(service: ConfigService, tmp_path: Path) -> None:
    SynaprConfig(project_name="On Disk").save(tmp_path / "synapr.config.json")
    service.reload()

    assert service.config.project_name == "On Disk"


def test_listeners_are_notified(service: ConfigService) -> None:
    seen: list[str] = []
    service.subscribe(lambda cfg: seen.append(cfg.project_name))

    service.update({"project_name": "Observed"}, persist=False)

    assert seen == ["Observed"]


def test_listener_failure_does_not_break_updates(service: ConfigService) -> None:
    def explode(_cfg: SynaprConfig) -> None:
        raise RuntimeError("boom")

    service.subscribe(explode)
    service.update({"project_name": "Still Works"}, persist=False)

    assert service.config.project_name == "Still Works"


# --------------------------------------------------------------------------- secrets


def test_snapshot_redacts_secrets(service: ConfigService) -> None:
    service.update({"gateway": {"openai_api_key": "sk-secret-value-4321"}}, persist=False)
    snapshot = service.snapshot()

    assert snapshot["config"]["gateway"]["openai_api_key"].startswith(SECRET_MASK)
    assert snapshot["meta"]["secrets"]["gateway.openai_api_key"] is True
    assert "sk-secret-value-4321" not in json.dumps(snapshot)


def test_masked_secret_roundtrip_is_not_destructive(service: ConfigService) -> None:
    service.update({"gateway": {"openai_api_key": "sk-secret-value-4321"}}, persist=False)
    redacted = service.snapshot()["config"]

    service.update(redacted, persist=False)

    assert service.config.gateway.openai_api_key == "sk-secret-value-4321"


# --------------------------------------------------------------------------- environment


def test_apply_env_values_updates_live_config(service: ConfigService) -> None:
    service.apply_env_values({"SYNAPR_PROVIDER": "ollama"})

    assert service.config.gateway.default_provider == "ollama"
    assert service.summary()["env_overrides"]["gateway.default_provider"] == "SYNAPR_PROVIDER"


def test_apply_env_values_persists_to_env_file(service: ConfigService, tmp_path: Path) -> None:
    service.apply_env_values({"SYNAPR_UI_PORT": "9321"}, persist_to_env_file=True)

    content = (tmp_path / ".env").read_text(encoding="utf-8")
    assert "SYNAPR_UI_PORT=9321" in content
    assert service.config.ui.port == 9321


def test_unset_env_value_restores_config(service: ConfigService) -> None:
    service.apply_env_values({"SYNAPR_PROVIDER": "groq"})
    service.apply_env_values({}, remove=["SYNAPR_PROVIDER"])

    assert service.config.gateway.default_provider == "mock"
    assert "gateway.default_provider" not in service.summary()["env_overrides"]


def test_apply_env_values_rejects_foreign_variables(service: ConfigService) -> None:
    with pytest.raises(ConfigServiceError):
        service.apply_env_values({"PATH": "/tmp"})


def test_legacy_alias_is_accepted(service: ConfigService) -> None:
    service.apply_env_values({"OLLAMA_BASE_URL": "http://ollama.internal:11434"})

    assert service.config.gateway.ollama_base_url == "http://ollama.internal:11434"


def test_load_env_file_through_service(service: ConfigService, tmp_path: Path) -> None:
    (tmp_path / ".env").write_text("SYNAPR_PROJECT_NAME=From Dotenv\n", encoding="utf-8")

    loaded = service.load_env_file()

    assert loaded["SYNAPR_PROJECT_NAME"] == "From Dotenv"
    assert service.config.project_name == "From Dotenv"


def test_env_report_is_complete(service: ConfigService) -> None:
    names = {item["name"] for item in service.env_report()}

    assert {"SYNAPR_PROVIDER", "SYNAPR_UI_PORT", "SYNAPR_OPENAI_API_KEY"} <= names


# --------------------------------------------------------------------------- schema


def test_schema_covers_every_section_and_field(service: ConfigService) -> None:
    schema = service.schema()
    keys = [section["key"] for section in schema["sections"]]

    assert keys == ["general", "gateway", "worktree", "editor", "perception", "pipeline", "ui"]
    gateway = next(s for s in schema["sections"] if s["key"] == "gateway")
    assert len(gateway["fields"]) == len(SynaprConfig().gateway.model_fields)


def test_schema_widgets_and_metadata(service: ConfigService) -> None:
    fields = {
        field["path"]: field
        for section in service.schema(editor_ids=["vscode", "cursor"])["sections"]
        for field in section["fields"]
    }

    assert fields["gateway.default_provider"]["widget"] == "select"
    assert "ollama" in fields["gateway.default_provider"]["options"]
    assert fields["gateway.openai_api_key"]["widget"] == "password"
    assert fields["gateway.openai_api_key"]["secret"] is True
    assert fields["pipeline.auto_test"]["widget"] == "boolean"
    assert fields["gateway.critic_models"]["widget"] == "list"
    assert fields["editor.editor_overrides"]["widget"] == "keyvalue"
    assert fields["ui.port"]["widget"] == "number"
    assert fields["ui.port"]["max"] == 65535
    assert fields["editor.preferred_editor"]["options"] == ["", "vscode", "cursor"]
    assert fields["gateway.planner_model"]["env"] == "SYNAPR_PLANNER_MODEL"
    assert fields["pipeline.default_test_command"]["nullable"] is True


def test_schema_marks_env_locked_fields(service: ConfigService) -> None:
    service.apply_env_values({"SYNAPR_PROVIDER": "vllm"})
    fields = {
        field["path"]: field
        for section in service.schema()["sections"]
        for field in section["fields"]
    }

    assert fields["gateway.default_provider"]["env_locked"] is True
    assert fields["gateway.default_provider"]["env_locked_by"] == "SYNAPR_PROVIDER"


def test_schema_never_exposes_secret_values(service: ConfigService) -> None:
    service.update({"gateway": {"groq_api_key": "gsk_secret_value_000"}}, persist=False)
    schema = json.dumps(service.schema())

    assert "gsk_secret_value_000" not in schema


# --------------------------------------------------------------------------- diagnostics


def test_test_provider_mock_is_always_available(service: ConfigService) -> None:
    result = service.test_provider("mock")

    assert result["ok"] is True
    assert result["provider"] == "mock"


def test_test_provider_requires_api_key(service: ConfigService) -> None:
    result = service.test_provider("groq")

    assert result["ok"] is False
    assert "API key" in result["detail"]


def test_test_provider_rejects_unknown(service: ConfigService) -> None:
    assert service.test_provider("telepathy")["ok"] is False


def test_test_provider_handles_unreachable_endpoint(service: ConfigService) -> None:
    service.update({"gateway": {"ollama_base_url": "http://127.0.0.1:1"}}, persist=False)

    result = service.test_provider("ollama", timeout=1.0)

    assert result["ok"] is False
    assert "Unreachable" in result["detail"]


def test_summary_reports_provenance(service: ConfigService, tmp_path: Path) -> None:
    summary = service.summary()

    assert summary["target_path"] == str(tmp_path / "synapr.config.json")
    assert summary["config_file_exists"] is False
    assert summary["local_only"] is True
    assert summary["writes_allowed"] is True
