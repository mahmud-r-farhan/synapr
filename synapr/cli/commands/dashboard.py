"""Dashboard startup command and lazy FastAPI import."""

from __future__ import annotations

import threading
import time
import webbrowser
from typing import Any

import click
import uvicorn

from synapr.cli.app import _service, main


@main.command()
@click.option("--host", default=None, help="Bind host address (default: ui.host).")
@click.option("--port", default=None, type=int, help="Port to run web dashboard on (default: ui.port).")
@click.option(
    "--open-browser/--no-open-browser",
    "open_browser",
    default=None,
    help="Open the dashboard in the default browser (default: ui.auto_open_browser).",
)
@click.option("--reload", "use_reload", is_flag=True, default=False, help="Enable auto-reload (development).")
@click.pass_context
def ui(
    ctx: click.Context,
    host: str | None,
    port: int | None,
    open_browser: bool | None,
    use_reload: bool,
) -> None:
    """Launch the Synapr local web dashboard and visual configurator."""
    service = _service(ctx)
    cfg = service.config
    bind_host = host or cfg.ui.host
    bind_port = port if port is not None else cfg.ui.port
    should_open = cfg.ui.auto_open_browser if open_browser is None else open_browser

    # Not a bind call: only maps wildcard binds to a clickable loopback URL.
    display_host = "127.0.0.1" if bind_host in {"0.0.0.0", "::"} else bind_host  # nosec B104
    url = f"http://{display_host}:{bind_port}"
    click.echo(click.style(f"\n⚡ Synapr Dashboard starting at {url}", bold=True, fg="magenta"))
    click.echo("   Configuration tab: edit providers, models, worktrees and env vars visually.")
    click.echo("   Press Ctrl+C to terminate.\n")

    if should_open:
        def _open() -> None:
            time.sleep(1.2)
            try:
                webbrowser.open(url)
            except Exception:  # pragma: no cover - headless hosts
                pass

        threading.Thread(target=_open, daemon=True).start()

    uvicorn.run(
        "synapr.web.app:app" if use_reload else _load_app(),
        host=bind_host,
        port=bind_port,
        log_level="warning",
        reload=use_reload,
    )


def _load_app() -> Any:
    """Import the FastAPI application lazily so CLI start-up stays fast."""
    from synapr.web.app import app

    return app
