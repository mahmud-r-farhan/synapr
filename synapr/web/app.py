"""FastAPI composition root for Synapr's modular dashboard API."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from synapr import __version__
from synapr.core.config_service import get_config_service
from synapr.web.models import (  # noqa: F401
    ConfigUpdateRequest,
    ConfigValueRequest,
    EmailDraftRequest,
    EmailSendRequest,
    EnvUpdateRequest,
    FetchUrlRequest,
    GoalRequest,
    LocalhostValidateRequest,
    ProviderTestRequest,
    SearchRequest,
    WorktreeActionRequest,
)
from synapr.web.routes import config, core, dashboard, events, github, mail, research
from synapr.web.settings import LOCAL_ORIGIN_REGEX, STATIC_DIR
from synapr.web.state import get_orchestrator

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

@app.get("/assets/index.html", include_in_schema=False)
async def dashboard_asset_index() -> HTMLResponse:
    """Serve the assembled page when the static index is requested directly."""
    return HTMLResponse(content=dashboard.load_dashboard_html())


if STATIC_DIR.is_dir():
    app.mount("/assets", StaticFiles(directory=str(STATIC_DIR)), name="assets")


@app.get("/favicon.ico", include_in_schema=False)
async def favicon() -> FileResponse:
    """Serve the local application icon as the web favicon."""
    ico_path = STATIC_DIR / "image.ico"
    if not ico_path.is_file():
        ico_path = STATIC_DIR.parent.parent / "assets" / "image.ico"
    if ico_path.is_file():
        return FileResponse(ico_path, media_type="image/x-icon")
    raise HTTPException(status_code=404, detail="Favicon not found")


for _routes in (core.router, config.router, events.router, research.router, github.router, mail.router, dashboard.router):
    app.include_router(_routes)

_COMPAT_MODULES = (core, config, events, research, github, mail, dashboard)


def __getattr__(name: str) -> Any:
    """Expose the former route-level module API and lazy orchestrator alias."""
    if name == "orchestrator":
        return get_orchestrator()
    for module in _COMPAT_MODULES:
        if hasattr(module, name):
            return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


load_dashboard_html = dashboard.load_dashboard_html
DASHBOARD_HTML = load_dashboard_html()
