"""Integration tests for environment-variable HTTP endpoints."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from synapr.web.app import app


@pytest.fixture
def client(repo_workspace: Path) -> Iterator[TestClient]:
    """TestClient bound to an isolated git workspace and configuration service."""
    with TestClient(app) as test_client:
        yield test_client


def test_env_listing(client: TestClient) -> None:
    payload = client.get("/api/config/env").json()
    names = {item["name"] for item in payload["variables"]}

    assert "SYNAPR_PROVIDER" in names
    assert all("effective_value" in item for item in payload["variables"])


def test_env_set_and_unset(client: TestClient) -> None:
    response = client.post(
        "/api/config/env", json={"values": {"SYNAPR_PROVIDER": "lmstudio"}, "persist": False}
    )
    assert response.status_code == 200
    assert response.json()["config"]["gateway"]["default_provider"] == "lmstudio"

    response = client.post(
        "/api/config/env", json={"values": {}, "unset": ["SYNAPR_PROVIDER"], "persist": False}
    )
    assert response.json()["config"]["gateway"]["default_provider"] == "mock"


def test_env_persisted_to_dotenv(client: TestClient, repo_workspace: Path) -> None:
    client.post(
        "/api/config/env", json={"values": {"SYNAPR_UI_PORT": "9999"}, "persist": True}
    )

    assert "SYNAPR_UI_PORT=9999" in (repo_workspace / ".env").read_text(encoding="utf-8")


def test_env_rejects_foreign_variables(client: TestClient) -> None:
    response = client.post("/api/config/env", json={"values": {"PATH": "/tmp"}})

    assert response.status_code == 400
    assert "Refusing" in response.json()["detail"]


def test_env_example_download(client: TestClient) -> None:
    response = client.get("/api/config/env/example")

    assert response.status_code == 200
    assert "SYNAPR_PROVIDER" in response.text
