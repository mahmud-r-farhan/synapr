"""GitHub issue lookup, provisioning, and PR description endpoints."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, HTTPException

from synapr.core.events import bus
from synapr.web.state import get_orchestrator

router = APIRouter()
_github_service: Any = None


def get_github_service() -> Any:
    global _github_service
    if _github_service is None:
        from synapr.github.service import GitHubIssueService

        _github_service = GitHubIssueService(worktree_manager=get_orchestrator().worktree_mgr)
    return _github_service


@router.get("/api/github/issues")
async def api_github_issues(state: str = "open", limit: int = 15) -> list[dict[str, Any]]:
    """List GitHub repository issues."""
    svc = get_github_service()
    issues = await asyncio.to_thread(svc.list_issues, state=state, limit=limit)
    return [issue.model_dump() for issue in issues]


@router.get("/api/github/issues/{number}")
async def api_github_issue(number: int) -> dict[str, Any]:
    """Fetch details for a single GitHub issue."""
    svc = get_github_service()
    issue = await asyncio.to_thread(svc.get_issue, number)
    if not issue:
        raise HTTPException(status_code=404, detail=f"Issue #{number} not found")
    return issue.model_dump()


@router.post("/api/github/issues/{number}/solve")
async def api_github_solve_issue(number: int) -> dict[str, Any]:
    """Provision a dedicated worktree for an issue and inject AGENT_INSTRUCTIONS.md."""
    svc = get_github_service()
    try:
        result = await svc.solve_issue_in_worktree(number)
        bus.emit("github:issue_worktree_provisioned", result)
        return result
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/api/github/issues/{number}/pr")
async def api_github_issue_pr(number: int) -> dict[str, Any]:
    """Generate pull request description linking the resolved issue."""
    svc = get_github_service()
    pr = svc.prepare_pr_for_issue(number)
    data = pr.model_dump()
    data["head_branch"] = pr.branch
    data["base_branch"] = pr.base
    return data
