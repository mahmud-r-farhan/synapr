"""Unit and integration tests for master SynaprOrchestrator."""

import asyncio
from pathlib import Path

from synapr.config import SynaprConfig
from synapr.orchestrator import SynaprOrchestrator


def test_orchestrator_planning(temp_repo: Path) -> None:
    """Test full planning and consensus debate loop."""
    async def _test() -> None:
        cfg = SynaprConfig()
        cfg.gateway.default_provider = "mock"
        orch = SynaprOrchestrator(config=cfg, repo_root=str(temp_repo))

        plan = await orch.plan_goal("Build a Redis cache layer for user profiles")
        assert plan.id
        assert len(plan.subtasks) >= 2
        assert plan.final_consensus_score > 0.0

    asyncio.run(_test())


def test_orchestrator_end_to_end_dry_run(temp_repo: Path) -> None:
    """Test complete end-to-end swarm loop in dry-run mode."""
    async def _test() -> None:
        cfg = SynaprConfig()
        cfg.gateway.default_provider = "mock"
        cfg.worktree.worktree_root = ".test_worktrees"
        orch = SynaprOrchestrator(config=cfg, repo_root=str(temp_repo))

        summary = await orch.run_goal(
            goal="Implement health check endpoint and monitoring",
            dry_run=True,
            launch_editors=False,
        )
        assert summary["plan_id"]
        assert summary["total_tasks"] >= 2
        assert "subtasks" in summary

    asyncio.run(_test())
