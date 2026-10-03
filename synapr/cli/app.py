"""Click application root and shared per-invocation dependencies."""

from __future__ import annotations

import click

from synapr import __version__
from synapr.core.config_service import ConfigService, get_config_service, set_config_service
from synapr.orchestrator import SynaprOrchestrator


def _service(ctx: click.Context) -> ConfigService:
    """Return the configuration service for the current invocation."""
    config_path = ctx.obj.get("config_path") if ctx.obj else None
    if config_path:
        return set_config_service(ConfigService(config_path=config_path))
    return get_config_service()

def _orchestrator(ctx: click.Context) -> SynaprOrchestrator:
    """Build an orchestrator bound to the active configuration."""
    return SynaprOrchestrator(config=_service(ctx).config)

@click.group()
@click.option(
    "--config",
    "config_path",
    default=None,
    type=click.Path(dir_okay=False),
    help="Path to a synapr.config.json file (overrides auto-discovery).",
)
@click.version_option(version=__version__, prog_name="synapr")
@click.pass_context
def main(ctx: click.Context, config_path: str | None) -> None:
    """⚡ Synapr: Autonomous Local Multi-IDE AI Orchestrator."""
    ctx.ensure_object(dict)
    ctx.obj["config_path"] = config_path
