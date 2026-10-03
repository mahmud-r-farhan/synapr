"""FastAPI application providing REST APIs and Server-Sent Events for the web dashboard.

Beyond swarm telemetry, this app exposes a complete **visual configurator**: every
setting declared in :mod:`synapr.config` can be inspected, edited, validated,
tested and persisted at runtime (``/api/config*``), including environment
variables, which can be injected live and optionally written to a git-ignored
``.env`` file.
"""

from __future__ import annotations

import asyncio
import json
import threading
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from synapr import __version__
from synapr.config import SynaprConfig, render_env_example
from synapr.core.config_service import ConfigServiceError, get_config_service
from synapr.core.events import Event, bus
from synapr.core.logger import logger
from synapr.orchestrator import SynaprOrchestrator

STATIC_DIR = Path(__file__).resolve().parent / "static"
LOCAL_ORIGIN_REGEX = r"^https?://(localhost|127\.0\.0\.1|\[::1\])(:\d+)?$"

app = FastAPI(
    title="Synapr Swarm Orchestrator",
    version=__version__,
    description="Local Autonomous Multi-IDE AI Orchestration Gateway & Control Center",
)


def _cors_settings() -> dict[str, Any]:
    """Keep the API locked to localhost unless the operator opts in explicitly."""
    try:
        allow_remote = get_config_service().config.ui.allow_remote_origins
    except Exception:  # pragma: no cover - configuration is best effort here
        allow_remote = False
    if allow_remote:
        return {"allow_origins": ["*"], "allow_credentials": False}
    return {"allow_origin_regex": LOCAL_ORIGIN_REGEX, "allow_credentials": True}


app.add_middleware(
    CORSMiddleware,
    allow_methods=["*"],
    allow_headers=["*"],
    **_cors_settings(),
)

if STATIC_DIR.is_dir():
    app.mount("/assets", StaticFiles(directory=str(STATIC_DIR)), name="assets")


@app.get("/favicon.ico", include_in_schema=False)
async def favicon() -> FileResponse:
    """Serve the local application icon as the web favicon."""
    ico_path = STATIC_DIR / "image.ico"
    if not ico_path.is_file():
        ico_path = Path(__file__).resolve().parent.parent / "assets" / "image.ico"
    if ico_path.is_file():
        return FileResponse(ico_path, media_type="image/x-icon")
    raise HTTPException(status_code=404, detail="Favicon not found")


# --------------------------------------------------------------------------------------
# Orchestrator lifecycle (hot-reloaded whenever the configuration changes)
# --------------------------------------------------------------------------------------

_orchestrator: SynaprOrchestrator | None = None
_bound_service: Any = None
_orchestrator_lock = threading.RLock()
_config_lock = asyncio.Lock()


def _on_config_changed(config: SynaprConfig) -> None:
    """Propagate configuration changes into the live orchestrator."""
    with _orchestrator_lock:
        if _orchestrator is not None:
            _orchestrator.apply_config(config)


def get_orchestrator() -> SynaprOrchestrator:
    """Return the shared orchestrator, rebuilding it if the config service changed."""
    global _orchestrator, _bound_service
    service = get_config_service()
    with _orchestrator_lock:
        if _orchestrator is None or _bound_service is not service:
            _orchestrator = SynaprOrchestrator(config=service.config)
            service.subscribe(_on_config_changed)
            _bound_service = service
        return _orchestrator


def __getattr__(name: str) -> Any:
    """Expose ``orchestrator`` lazily for backwards compatibility."""
    if name == "orchestrator":
        return get_orchestrator()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


# --------------------------------------------------------------------------------------
# Request models
# --------------------------------------------------------------------------------------


class GoalRequest(BaseModel):
    goal: str
    context: str | None = None
    dry_run: bool = False
    launch_editors: bool = True


class WorktreeActionRequest(BaseModel):
    task_id: str | None = None
    force: bool = True
    delete_branch: bool = False


class ConfigUpdateRequest(BaseModel):
    """Partial configuration payload merged into the active configuration."""

    config: dict[str, Any] = Field(default_factory=dict)
    persist: bool = True


class ConfigValueRequest(BaseModel):
    """Single dotted-path assignment (``gateway.planner_model``)."""

    path: str
    value: Any = None
    persist: bool = True


class EnvUpdateRequest(BaseModel):
    """Runtime environment variable declaration, optionally stored in ``.env``."""

    values: dict[str, str] = Field(default_factory=dict)
    unset: list[str] = Field(default_factory=list)
    persist: bool = False
    env_file: str = ".env"


class ProviderTestRequest(BaseModel):
    provider: str | None = None


# --------------------------------------------------------------------------------------
# Core endpoints
# --------------------------------------------------------------------------------------


@app.get("/api/health")
async def health() -> dict[str, Any]:
    """Lightweight liveness probe used by the dashboard and CI smoke tests."""
    return {"status": "ok", "version": __version__}


@app.get("/api/status")
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


@app.get("/api/editors")
async def list_editors() -> list[dict[str, Any]]:
    """List all detected and configured code editors."""
    return [e.model_dump() for e in get_orchestrator().get_installed_editors()]


@app.post("/api/editors/rescan")
async def rescan_editors() -> list[dict[str, Any]]:
    """Re-scan the host machine for installed editors (after a config change)."""
    orch = get_orchestrator()
    await asyncio.to_thread(orch.registry.refresh)
    return [e.model_dump() for e in orch.get_installed_editors()]


@app.get("/api/worktrees")
async def list_worktrees() -> list[dict[str, Any]]:
    """Query git worktree allocations (empty when the host is not a git repository)."""
    try:
        return await get_orchestrator().worktree_mgr.list_worktrees()
    except Exception as exc:
        logger.warning(f"Unable to list git worktrees: {exc}")
        return []


@app.post("/api/plan")
async def create_plan(req: GoalRequest) -> dict[str, Any]:
    """Decompose goal and run multi-LLM debate without launching editors."""
    if not req.goal.strip():
        raise HTTPException(status_code=400, detail="Goal cannot be empty")
    plan = await get_orchestrator().plan_goal(req.goal, req.context)
    return plan.model_dump()


@app.post("/api/execute")
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


@app.post("/api/worktrees/clean")
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


# --------------------------------------------------------------------------------------
# Visual configurator endpoints
# --------------------------------------------------------------------------------------


def _guard_writes() -> None:
    """Reject mutations when the operator disabled dashboard configuration writes."""
    if not get_config_service().config.ui.allow_config_writes:
        raise HTTPException(
            status_code=403,
            detail="Configuration editing is disabled (ui.allow_config_writes = false).",
        )


@app.get("/api/config")
async def read_config() -> dict[str, Any]:
    """Return the active configuration with secrets redacted, plus provenance metadata."""
    return get_config_service().snapshot(redact=True)


@app.get("/api/config/schema")
async def config_schema() -> dict[str, Any]:
    """Return a declarative form description so the dashboard can render every field."""
    orch = get_orchestrator()
    editor_ids = [editor.id for editor in orch.get_installed_editors()]
    return get_config_service().schema(editor_ids=editor_ids)


@app.put("/api/config")
async def update_config(req: ConfigUpdateRequest) -> dict[str, Any]:
    """Validate and apply a partial configuration update, optionally persisting it."""
    _guard_writes()
    service = get_config_service()
    async with _config_lock:
        try:
            await asyncio.to_thread(service.update, req.config, persist=req.persist)
        except ConfigServiceError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except OSError as exc:
            raise HTTPException(status_code=500, detail=f"Failed to persist: {exc}") from exc
    return service.snapshot(redact=True)


@app.post("/api/config/value")
async def set_config_value(req: ConfigValueRequest) -> dict[str, Any]:
    """Set a single configuration field by dotted path."""
    _guard_writes()
    service = get_config_service()
    async with _config_lock:
        try:
            await asyncio.to_thread(service.set_value, req.path, req.value, persist=req.persist)
        except ConfigServiceError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    return service.snapshot(redact=True)


@app.post("/api/config/reset")
async def reset_config(persist: bool = False) -> dict[str, Any]:
    """Restore built-in defaults (environment variables are re-applied on top)."""
    _guard_writes()
    service = get_config_service()
    async with _config_lock:
        await asyncio.to_thread(service.reset, persist=persist)
    return service.snapshot(redact=True)


@app.post("/api/config/reload")
async def reload_config() -> dict[str, Any]:
    """Discard in-memory changes and reload the configuration file from disk."""
    service = get_config_service()
    async with _config_lock:
        await asyncio.to_thread(service.reload)
    return service.snapshot(redact=True)


@app.post("/api/config/save")
async def save_config() -> dict[str, Any]:
    """Persist the in-memory configuration to the project configuration file."""
    _guard_writes()
    service = get_config_service()
    async with _config_lock:
        try:
            path = await asyncio.to_thread(service.persist)
        except OSError as exc:
            raise HTTPException(status_code=500, detail=f"Failed to persist: {exc}") from exc
    return {"status": "saved", "path": str(path), **service.snapshot(redact=True)}


@app.get("/api/config/env")
async def read_env() -> dict[str, Any]:
    """List every supported environment variable with its current state."""
    service = get_config_service()
    return {"variables": service.env_report(), "meta": service.summary()}


@app.post("/api/config/env")
async def write_env(req: EnvUpdateRequest) -> dict[str, Any]:
    """Declare environment variables at runtime and optionally store them in ``.env``."""
    _guard_writes()
    service = get_config_service()
    async with _config_lock:
        try:
            await asyncio.to_thread(
                service.apply_env_values,
                req.values,
                persist_to_env_file=req.persist,
                env_file=req.env_file,
                remove=req.unset,
            )
        except ConfigServiceError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except OSError as exc:
            raise HTTPException(status_code=500, detail=f"Failed to write env file: {exc}") from exc
    return {"variables": service.env_report(), **service.snapshot(redact=True)}


@app.get("/api/config/env/example", response_class=PlainTextResponse)
async def env_example() -> str:
    """Download a documented ``.env.example`` describing every variable."""
    return render_env_example()


@app.post("/api/config/test-provider")
async def test_provider(req: ProviderTestRequest) -> dict[str, Any]:
    """Probe an LLM provider endpoint and report reachability and available models."""
    service = get_config_service()
    return await asyncio.to_thread(service.test_provider, req.provider)


# --------------------------------------------------------------------------------------
# Telemetry stream & dashboard
# --------------------------------------------------------------------------------------


@app.get("/api/events")
async def stream_events(request: Request) -> StreamingResponse:
    """Server-Sent Events (SSE) stream for real-time dashboard telemetry."""

    async def event_generator() -> AsyncGenerator[str, None]:
        q: asyncio.Queue[Event] = asyncio.Queue()

        def _on_event(ev: Event) -> None:
            try:
                q.put_nowait(ev)
            except Exception:
                pass

        bus.subscribe("*", _on_event)
        try:
            # Yield initial connection event
            yield f"event: connected\ndata: {json.dumps({'message': 'Connected to Synapr SSE Stream'})}\n\n"

            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(q.get(), timeout=20.0)
                    yield f"event: {event.event_type}\ndata: {json.dumps(event.data)}\n\n"
                except TimeoutError:
                    # Keep-alive heartbeat ping
                    yield ": ping\n\n"
        finally:
            bus.unsubscribe("*", _on_event)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


# --------------------------------------------------------------------------------------
# Web Search & Browser Automation APIs (FUTURE_EXPANSIONS.md #3)
# --------------------------------------------------------------------------------------


class SearchRequest(BaseModel):
    query: str
    limit: int = 5
    fetch_content: bool = True


class FetchUrlRequest(BaseModel):
    url: str
    max_chars: int = 12000


class LocalhostValidateRequest(BaseModel):
    url: str = "http://localhost:3000"


@app.get("/api/search")
async def api_search_get(q: str, limit: int = 5) -> dict[str, Any]:
    """Execute live web search for LLM context or user inquiry."""
    from synapr.browser.search import search_web

    results = await asyncio.to_thread(search_web, q, max_results=min(limit, 20))
    return {"query": q, "count": len(results), "results": [r.model_dump() for r in results]}


@app.post("/api/search")
async def api_search_post(req: SearchRequest) -> dict[str, Any]:
    """Search the web and optionally fetch text excerpts from the top pages."""
    gateway = get_orchestrator().gateway
    return await gateway.search_and_research(
        query=req.query, max_results=req.limit, fetch_content=req.fetch_content
    )


@app.post("/api/fetch-url")
async def api_fetch_url(req: FetchUrlRequest) -> dict[str, Any]:
    """Fetch an arbitrary webpage and extract clean markdown text for analysis."""
    from synapr.browser.search import fetch_webpage

    page = await asyncio.to_thread(fetch_webpage, req.url, max_chars=req.max_chars)
    data = page.model_dump()
    data["markdown"] = page.text
    return data


@app.post("/api/browser/validate-localhost")
async def api_validate_localhost(req: LocalhostValidateRequest) -> dict[str, Any]:
    """Inspect local development server health and scan for runtime crash indicators."""
    from synapr.browser.engine import validate_localhost

    result = await asyncio.to_thread(validate_localhost, req.url)
    data = result.model_dump()
    data["is_healthy"] = result.is_healthy
    data["errors_detected"] = result.errors_detected
    return data


# --------------------------------------------------------------------------------------
# GitHub Issue & PR Lifecycle APIs (FUTURE_EXPANSIONS.md #5)
# --------------------------------------------------------------------------------------

_github_service: Any = None


def get_github_service() -> Any:
    global _github_service
    if _github_service is None:
        from synapr.github.service import GitHubIssueService

        _github_service = GitHubIssueService(worktree_manager=get_orchestrator().worktree_mgr)
    return _github_service


@app.get("/api/github/issues")
async def api_github_issues(state: str = "open", limit: int = 15) -> list[dict[str, Any]]:
    """List GitHub repository issues."""
    svc = get_github_service()
    issues = await asyncio.to_thread(svc.list_issues, state=state, limit=limit)
    return [issue.model_dump() for issue in issues]


@app.get("/api/github/issues/{number}")
async def api_github_issue(number: int) -> dict[str, Any]:
    """Fetch details for a single GitHub issue."""
    svc = get_github_service()
    issue = await asyncio.to_thread(svc.get_issue, number)
    if not issue:
        raise HTTPException(status_code=404, detail=f"Issue #{number} not found")
    return issue.model_dump()


@app.post("/api/github/issues/{number}/solve")
async def api_github_solve_issue(number: int) -> dict[str, Any]:
    """Provision a dedicated worktree for an issue and inject AGENT_INSTRUCTIONS.md."""
    svc = get_github_service()
    try:
        result = await svc.solve_issue_in_worktree(number)
        bus.emit("github:issue_worktree_provisioned", result)
        return result
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/github/issues/{number}/pr")
async def api_github_issue_pr(number: int) -> dict[str, Any]:
    """Generate pull request description linking the resolved issue."""
    svc = get_github_service()
    pr = svc.prepare_pr_for_issue(number)
    data = pr.model_dump()
    data["head_branch"] = pr.branch
    data["base_branch"] = pr.base
    return data


# --------------------------------------------------------------------------------------
# Email Gateway & Draft Assistant APIs (FUTURE_EXPANSIONS.md #4)
# --------------------------------------------------------------------------------------

_email_service: Any = None


def get_email_service() -> Any:
    global _email_service
    if _email_service is None:
        from synapr.email_gateway.service import EmailGatewayService

        _email_service = EmailGatewayService()
    return _email_service


class EmailDraftRequest(BaseModel):
    developer_notes: str = ""


class EmailSendRequest(BaseModel):
    confirm: bool = False


@app.get("/api/mail/messages")
async def api_mail_messages(folder: str = "inbox") -> list[dict[str, Any]]:
    """List incoming customer and client requirement messages."""
    svc = get_email_service()
    msgs = await asyncio.to_thread(svc.list_messages, folder=folder)
    return [m.model_dump() for m in msgs]


@app.get("/api/mail/messages/{message_id}")
async def api_mail_message(message_id: str) -> dict[str, Any]:
    """Retrieve an email message by ID."""
    svc = get_email_service()
    msg = await asyncio.to_thread(svc.get_message, message_id)
    if not msg:
        raise HTTPException(status_code=404, detail=f"Message {message_id} not found")
    return msg.model_dump()


@app.post("/api/mail/messages/{message_id}/triage")
async def api_mail_triage(message_id: str) -> dict[str, Any]:
    """Classify email message into structured engineering brief."""
    svc = get_email_service()
    try:
        res = await asyncio.to_thread(svc.triage_message, message_id)
        data = res.model_dump()
        data["urgency"] = res.priority
        data["executive_summary"] = res.summary
        data["action_items"] = res.actionable_items
        return data
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/mail/drafts")
async def api_mail_drafts() -> list[dict[str, Any]]:
    """List prepared response drafts."""
    svc = get_email_service()
    drafts = await asyncio.to_thread(svc.list_drafts)
    return [d.model_dump() for d in drafts]


@app.post("/api/mail/messages/{message_id}/draft")
async def api_mail_create_draft(message_id: str, req: EmailDraftRequest) -> dict[str, Any]:
    """Generate a context-aware technical draft response strictly to Drafts."""
    svc = get_email_service()
    orch = get_orchestrator()
    summary = get_config_service().summary()
    repo_ctx = f"Branch: {orch.config.worktree.base_branch} | Provider: {summary['provider']}"
    try:
        draft = await asyncio.to_thread(
            svc.generate_draft,
            message_id,
            developer_notes=req.developer_notes,
            repo_context=repo_ctx,
        )
        data = draft.model_dump()
        data["recipient"] = draft.to
        return data
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/mail/drafts/{draft_id}/send")
async def api_mail_send_draft(draft_id: str, req: EmailSendRequest) -> dict[str, Any]:
    """Safe dispatch gate: Outbound transmission blocked unless confirm=True."""
    svc = get_email_service()
    try:
        res = await asyncio.to_thread(svc.send_draft, draft_id, confirm=req.confirm)
        if "recipient" not in res and "to" in res:
            res["recipient"] = res["to"]
        return res
    except RuntimeError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


_FALLBACK_HTML = (
    "<!DOCTYPE html><html><head><meta charset='utf-8'><title>Synapr</title></head>"
    "<body style='font-family:sans-serif;background:#090d16;color:#f1f5f9;padding:2rem'>"
    "<h1>⚡ Synapr</h1><p>Dashboard assets are missing from this installation. "
    "The REST API remains available under <code>/api</code>.</p></body></html>"
)


def load_dashboard_html() -> str:
    """Read the dashboard markup from the packaged static assets."""
    index = STATIC_DIR / "index.html"
    try:
        return index.read_text(encoding="utf-8")
    except OSError:  # pragma: no cover - only when assets are stripped
        return _FALLBACK_HTML


@app.get("/", response_class=HTMLResponse)
async def serve_dashboard() -> HTMLResponse:
    """Serve the single-page application dashboard."""
    return HTMLResponse(content=load_dashboard_html())


DASHBOARD_HTML = load_dashboard_html()
"""Rendered dashboard markup (kept for backwards compatibility)."""
