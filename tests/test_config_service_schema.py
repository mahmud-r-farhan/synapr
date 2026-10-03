"""Tests for declarative configuration schema generation."""

import json
from pathlib import Path

import pytest

from synapr.config import SynaprConfig
from synapr.core.config_service import ConfigService


@pytest.fixture
def service(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> ConfigService:
    monkeypatch.chdir(tmp_path)
    return ConfigService(base_dir=tmp_path)


def test_schema_covers_every_section_and_field(service: ConfigService) -> None:
    schema = service.schema()
    keys = [section["key"] for section in schema["sections"]]

    assert keys == [
        "general",
        "gateway",
        "worktree",
        "editor",
        "perception",
        "pipeline",
        "ui",
        "browser",
        "email",
        "github",
    ]
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
