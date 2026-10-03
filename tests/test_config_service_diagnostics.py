"""Tests for provider probes and configuration provenance."""

from pathlib import Path

import pytest

from synapr.core.config_service import ConfigService


@pytest.fixture
def service(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> ConfigService:
    monkeypatch.chdir(tmp_path)
    return ConfigService(base_dir=tmp_path)


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
