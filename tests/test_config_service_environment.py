"""Tests for configuration snapshots and runtime environment updates."""

import json
from pathlib import Path

import pytest

from synapr.config import SECRET_MASK
from synapr.core.config_service import ConfigService, ConfigServiceError


@pytest.fixture
def service(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> ConfigService:
    monkeypatch.chdir(tmp_path)
    return ConfigService(base_dir=tmp_path)


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
