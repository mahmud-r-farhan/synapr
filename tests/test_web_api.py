"""Unit tests for FastAPI endpoint handlers."""

import asyncio

from synapr.web.app import GoalRequest, create_plan, get_status, list_editors, list_worktrees


def test_api_status_endpoint() -> None:
    """Test /api/status endpoint response."""
    async def _test() -> None:
        status_data = await get_status()
        assert status_data["status"] == "online"
        assert "version" in status_data
        assert "discovered_editors_count" in status_data

    asyncio.run(_test())


def test_api_editors_endpoint() -> None:
    """Test /api/editors endpoint returns list of editors."""
    async def _test() -> None:
        editors = await list_editors()
        assert isinstance(editors, list)

    asyncio.run(_test())


def test_api_worktrees_endpoint() -> None:
    """Test /api/worktrees endpoint."""
    async def _test() -> None:
        worktrees = await list_worktrees()
        assert isinstance(worktrees, list)

    asyncio.run(_test())


def test_api_plan_endpoint() -> None:
    """Test /api/plan endpoint decomposition and debate."""
    async def _test() -> None:
        req = GoalRequest(goal="Add telemetry metrics endpoint", dry_run=True)
        plan_data = await create_plan(req)
        assert plan_data["id"]
        assert len(plan_data["subtasks"]) >= 1

    asyncio.run(_test())
