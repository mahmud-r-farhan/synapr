"""Tests for configuration service lifecycle, validation, and updates."""

import json
from pathlib import Path

import pytest

from synapr.config import SynaprConfig
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
