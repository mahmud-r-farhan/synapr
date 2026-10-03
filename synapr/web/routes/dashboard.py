"""Dashboard markup composition and root-page endpoint."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from synapr.web.settings import STATIC_DIR

router = APIRouter()


_FALLBACK_HTML = (
    "<!DOCTYPE html><html><head><meta charset='utf-8'><title>Synapr</title></head>"
    "<body style='font-family:sans-serif;background:#090d16;color:#f1f5f9;padding:2rem'>"
    "<h1>⚡ Synapr</h1><p>Dashboard assets are missing from this installation. "
    "The REST API remains available under <code>/api</code>.</p></body></html>"
)


def load_dashboard_html() -> str:
    """Assemble the dashboard shell with its independently maintained views."""
    try:
        page = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
        for section in ("swarm", "research", "github", "email", "config", "environment"):
            marker = f"    <!-- SYNAPR:{section} -->"
            fragment = (STATIC_DIR / f"{section}.html").read_text(encoding="utf-8")
            page = page.replace(marker, fragment.rstrip())
        return page
    except OSError:  # pragma: no cover - only when packaged assets are stripped
        return _FALLBACK_HTML


@router.get("/", response_class=HTMLResponse)
async def serve_dashboard() -> HTMLResponse:
    """Serve the single-page application dashboard."""
    return HTMLResponse(content=load_dashboard_html())
