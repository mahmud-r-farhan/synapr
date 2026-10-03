"""Tests covering live configuration reloads inside the orchestrator and SSE stream."""

import json
from pathlib import Path

from fastapi.testclient import TestClient

from synapr.config import SynaprConfig
from synapr.core.config_service import ConfigService, get_config_service
from synapr.core.events import bus
from synapr.orchestrator import SynaprOrchestrator
from synapr.web.app import app


def test_orchestrator_uses_shared_config_service(workspace: Path) -> None:
    get_config_service().update({"project_name": "Shared"}, persist=False)

    assert SynaprOrchestrator().config.project_name == "Shared"


def test_apply_config_rebuilds_subsystems(temp_repo: Path) -> None:
    orchestrator = SynaprOrchestrator(config=SynaprConfig(), repo_root=str(temp_repo))
    original_gateway = orchestrator.gateway
    orchestrator.active_plan = None

    updated = SynaprConfig()
    updated.gateway.default_provider = "ollama"
    updated.worktree.worktree_root = ".custom_worktrees"
    updated.pipeline.default_test_command = "pytest -x"
    orchestrator.apply_config(updated)

    assert orchestrator.gateway is not original_gateway
    assert orchestrator.gateway.config.default_provider == "ollama"
    assert orchestrator.worktree_mgr.config.worktree_root == ".custom_worktrees"
    assert orchestrator.test_pipeline.default_command == "pytest -x"


def test_config_change_propagates_to_live_orchestrator(repo_workspace: Path) -> None:
    with TestClient(app) as client:
        client.put(
            "/api/config",
            json={"config": {"worktree": {"branch_prefix": "swarm/"}}, "persist": False},
        )
        from synapr.web.app import get_orchestrator

        assert get_orchestrator().worktree_mgr.config.branch_prefix == "swarm/"


def test_event_bus_delivers_config_updates(workspace: Path) -> None:
    """The SSE stream is fed by the global event bus - verify what it will publish."""
    received: list[tuple[str, dict]] = []

    def listener(event) -> None:  # noqa: ANN001 - Event imported lazily below
        received.append((event.event_type, event.data))

    bus.subscribe("*", listener)
    try:
        get_config_service().update({"gateway": {"default_provider": "ollama"}}, persist=False)
    finally:
        bus.unsubscribe("*", listener)

    assert ("config:updated", {"reason": "update", "persisted": False, "provider": "ollama"}) in received
    assert json.dumps([data for _, data in received])  # payloads stay JSON serialisable


def test_service_swap_rebinds_orchestrator(tmp_path: Path, monkeypatch) -> None:
    from synapr.core.config_service import set_config_service
    from synapr.web.app import get_orchestrator

    monkeypatch.chdir(tmp_path)
    first = ConfigService(base_dir=tmp_path)
    set_config_service(first)
    first.update({"project_name": "First"}, persist=False)
    assert get_orchestrator().config.project_name == "First"

    second = ConfigService(base_dir=tmp_path)
    set_config_service(second)
    second.update({"project_name": "Second"}, persist=False)
    assert get_orchestrator().config.project_name == "Second"
