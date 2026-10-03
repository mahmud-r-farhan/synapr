"""Integration tests for provider probes and supporting HTTP endpoints."""

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


def test_provider_test_endpoint(client: TestClient) -> None:
    result = client.post("/api/config/test-provider", json={"provider": "mock"}).json()

    assert result["ok"] is True
    assert result["provider"] == "mock"


def test_editors_endpoints(client: TestClient) -> None:
    assert isinstance(client.get("/api/editors").json(), list)
    assert isinstance(client.post("/api/editors/rescan").json(), list)


def test_worktrees_endpoint(client: TestClient) -> None:
    assert isinstance(client.get("/api/worktrees").json(), list)


def test_plan_endpoint_rejects_empty_goal(client: TestClient) -> None:
    assert client.post("/api/plan", json={"goal": "   "}).status_code == 400


def test_execute_endpoint_queues_work(client: TestClient) -> None:
    response = client.post("/api/execute", json={"goal": "Add metrics", "dry_run": True})

    assert response.status_code == 200
    assert "initiated" in response.json()["message"]
