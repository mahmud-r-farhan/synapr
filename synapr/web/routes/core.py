"""Health, status, planning, execution, and worktree endpoints."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException

from synapr import __version__
from synapr.core.events import bus
from synapr.core.logger import logger
from synapr.web.models import GoalRequest, WorktreeActionRequest
from synapr.web.state import get_orchestrator

router = APIRouter()


@router.get("/api/health")
async def health() -> dict[str, Any]:
    """Lightweight liveness probe used by the dashboard and CI smoke tests."""
    return {"status": "ok", "version": __version__}


@router.get("/api/status")
async def get_status() -> dict[str, Any]:
    """Retrieve active system state, base branch, and orchestrator metrics."""
    orch = get_orchestrator()
    base_branch = await orch.worktree_mgr.detect_base_branch()
    git_available = True
    try:
        worktrees = await orch.worktree_mgr.list_worktrees()
    except Exception as exc:
        # The dashboard must stay usable outside a git repository.
        logger.warning(f"Unable to list git worktrees: {exc}")
        worktrees, git_available = [], False
    editors = orch.get_installed_editors()
    config = orch.config
    return {
        "status": "online",
        "git_available": git_available,
        "version": __version__,
        "repo_root": str(orch.repo_root),
        "project_name": config.project_name,
        "base_branch": base_branch,
        "active_worktrees_count": len(worktrees),
        "discovered_editors_count": len(editors),
        "active_plan": orch.active_plan.model_dump() if orch.active_plan else None,
        "provider": config.gateway.default_provider,
        "local_only": config.gateway.is_local_provider,
        "config_source": config.meta.source_path,
        "env_overrides": len(config.meta.env_overrides),
    }


@router.get("/api/editors")
async def list_editors() -> list[dict[str, Any]]:
    """List all detected and configured code editors."""
    return [e.model_dump() for e in get_orchestrator().get_installed_editors()]


@router.post("/api/editors/rescan")
async def rescan_editors() -> list[dict[str, Any]]:
    """Re-scan the host machine for installed editors (after a config change)."""
    orch = get_orchestrator()
    await asyncio.to_thread(orch.registry.refresh)
    return [e.model_dump() for e in orch.get_installed_editors()]


@router.get("/api/worktrees")
async def list_worktrees() -> list[dict[str, Any]]:
    """Query git worktree allocations (empty when the host is not a git repository)."""
    try:
        return await get_orchestrator().worktree_mgr.list_worktrees()
    except Exception as exc:
        logger.warning(f"Unable to list git worktrees: {exc}")
        return []


@router.post("/api/plan")
async def create_plan(req: GoalRequest) -> dict[str, Any]:
    """Decompose goal and run multi-LLM debate without launching editors."""
    if not req.goal.strip():
        raise HTTPException(status_code=400, detail="Goal cannot be empty")
    plan = await get_orchestrator().plan_goal(req.goal, req.context)
    return plan.model_dump()


@router.post("/api/execute")
async def execute_goal(req: GoalRequest, bg_tasks: BackgroundTasks) -> dict[str, Any]:
    """Execute end-to-end swarm loop."""
    if not req.goal.strip():
        raise HTTPException(status_code=400, detail="Goal cannot be empty")

    orch = get_orchestrator()

    # Run in background to maintain responsive API
    async def _run() -> None:
        try:
            await orch.run_goal(
                goal=req.goal,
                context=req.context,
                dry_run=req.dry_run,
                launch_editors=req.launch_editors,
            )
        except Exception as e:
            logger.error(f"Background swarm execution failed: {e}")
            bus.emit("orchestrator:error", {"error": str(e)})

    bg_tasks.add_task(_run)
    return {"message": "Swarm execution initiated in background", "goal": req.goal}


@router.post("/api/worktrees/clean")
async def cleanup_worktrees(req: WorktreeActionRequest) -> dict[str, Any]:
    """Clean specific or all stale worktrees."""
    orch = get_orchestrator()
    if req.task_id:
        await orch.worktree_mgr.cleanup_worktree(
            req.task_id, force=req.force, delete_branch=req.delete_branch
        )
        return {"status": "cleaned", "task_id": req.task_id}
    await orch.worktree_mgr.prune_all()
    return {"status": "pruned_all"}
