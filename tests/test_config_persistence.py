"""Tests for config file persistence and helper utilities."""

import json
import os
from pathlib import Path

import pytest
from pydantic import ValidationError

from synapr.config import (
    ENV_VAR_SPECS,
    SECRET_MASK,
    SynaprConfig,
    default_config_path,
    discover_config_file,
    env_var_report,
    get_by_path,
    render_env_example,
    set_by_path,
)


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
