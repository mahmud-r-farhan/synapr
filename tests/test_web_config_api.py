"""Integration tests for configuration and dashboard HTTP endpoints."""

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from synapr.config import SECRET_MASK
from synapr.web.app import app


@pytest.fixture
def client(repo_workspace: Path) -> Iterator[TestClient]:
    """TestClient bound to an isolated git workspace and configuration service."""
    with TestClient(app) as test_client:
        yield test_client


def test_health_and_status(client: TestClient) -> None:
    assert client.get("/api/health").json()["status"] == "ok"

    status = client.get("/api/status").json()
    assert status["status"] == "online"
    assert status["provider"] == "mock"
    assert status["local_only"] is True
    assert status["git_available"] is True


def test_dashboard_and_assets_are_served(client: TestClient) -> None:
    page = client.get("/")
    assert page.status_code == 200
    assert "Synapr" in page.text
    for script in (
        "app.js",
        "swarm.js",
        "config-fields.js",
        "config-actions.js",
        "environment.js",
        "research.js",
        "github.js",
        "email.js",
        "bootstrap.js",
    ):
        assert f"/assets/{script}" in page.text
    assert 'id="view-swarm"' in page.text
    assert 'id="view-env"' in page.text
    assert "SYNAPR:swarm" not in page.text

    asset_page = client.get("/assets/index.html")
    assert asset_page.status_code == 200
    assert asset_page.text == page.text
    for asset in (
        "app.js",
        "swarm.js",
        "config-fields.js",
        "config-actions.js",
        "environment.js",
        "research.js",
        "github.js",
        "email.js",
        "bootstrap.js",
        "styles.css",
        "styles-views.css",
        "swarm.html",
        "research.html",
        "github.html",
        "email.html",
        "config.html",
        "environment.html",
    ):
        assert client.get(f"/assets/{asset}").status_code == 200
    assert client.get("/favicon.ico").status_code == 200
    assert client.get("/assets/image.ico").status_code == 200


def test_dashboard_has_no_external_requests(client: TestClient) -> None:
    """Air-gapped guarantee: the dashboard must not pull remote assets."""
    page = client.get("/").text
    for marker in ("https://fonts.", "http://cdn.", "https://cdn.", "unpkg.com"):
        assert marker not in page


def test_read_config_redacts_secrets(client: TestClient) -> None:
    client.put(
        "/api/config",
        json={"config": {"gateway": {"openai_api_key": "sk-live-secret-7777"}}, "persist": False},
    )

    payload = client.get("/api/config").json()

    assert payload["config"]["gateway"]["openai_api_key"].startswith(SECRET_MASK)
    assert "sk-live-secret-7777" not in json.dumps(payload)
    assert payload["meta"]["secrets"]["gateway.openai_api_key"] is True


def test_schema_endpoint_describes_form(client: TestClient) -> None:
    schema = client.get("/api/config/schema").json()
    sections = {section["key"] for section in schema["sections"]}

    assert {"gateway", "worktree", "editor", "perception", "pipeline", "ui"} <= sections
    assert "ollama" in schema["providers"]


def test_update_applies_without_persisting(client: TestClient, repo_workspace: Path) -> None:
    response = client.put(
        "/api/config",
        json={"config": {"gateway": {"planner_model": "codellama:13b"}}, "persist": False},
    )

    assert response.status_code == 200
    assert response.json()["config"]["gateway"]["planner_model"] == "codellama:13b"
    assert not (repo_workspace / "synapr.config.json").exists()


def test_update_persists_to_disk(client: TestClient, repo_workspace: Path) -> None:
    response = client.put(
        "/api/config",
        json={"config": {"project_name": "Persisted Project"}, "persist": True},
    )

    assert response.status_code == 200
    payload = json.loads((repo_workspace / "synapr.config.json").read_text(encoding="utf-8"))
    assert payload["project_name"] == "Persisted Project"


def test_update_is_rejected_when_invalid(client: TestClient) -> None:
    response = client.put(
        "/api/config", json={"config": {"ui": {"port": 99999}}, "persist": False}
    )

    assert response.status_code == 400
    assert "port" in response.json()["detail"]


def test_update_takes_effect_in_orchestrator(client: TestClient) -> None:
    client.put(
        "/api/config",
        json={"config": {"gateway": {"default_provider": "ollama"}}, "persist": False},
    )

    assert client.get("/api/status").json()["provider"] == "ollama"


def test_set_single_value(client: TestClient) -> None:
    response = client.post(
        "/api/config/value",
        json={"path": "perception.enabled", "value": False, "persist": False},
    )

    assert response.status_code == 200
    assert response.json()["config"]["perception"]["enabled"] is False


def test_set_single_value_unknown_path(client: TestClient) -> None:
    response = client.post(
        "/api/config/value", json={"path": "nope.nope", "value": 1, "persist": False}
    )
    assert response.status_code == 400


def test_save_reset_and_reload_cycle(client: TestClient, repo_workspace: Path) -> None:
    client.put("/api/config", json={"config": {"project_name": "Saved"}, "persist": True})

    reset = client.post("/api/config/reset").json()
    assert reset["config"]["project_name"] == "Synapr Project"

    reloaded = client.post("/api/config/reload").json()
    assert reloaded["config"]["project_name"] == "Saved"

    client.put("/api/config", json={"config": {"project_name": "Second"}, "persist": False})
    saved = client.post("/api/config/save").json()
    assert saved["status"] == "saved"
    payload = json.loads((repo_workspace / "synapr.config.json").read_text(encoding="utf-8"))
    assert payload["project_name"] == "Second"


def test_writes_can_be_disabled(client: TestClient) -> None:
    client.put("/api/config", json={"config": {"ui": {"allow_config_writes": False}}, "persist": False})

    blocked = client.put("/api/config", json={"config": {"project_name": "Nope"}})
    assert blocked.status_code == 403

    # Read-only operations keep working, and reload restores an editable state.
    assert client.get("/api/config").status_code == 200
    assert client.post("/api/config/reload").status_code == 200
