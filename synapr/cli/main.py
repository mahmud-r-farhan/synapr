"""Click CLI interface for Synapr autonomous orchestrator."""

import asyncio
import os
import sys
import webbrowser
import click
import uvicorn
from synapr import __version__
from synapr.config import SynaprConfig
from synapr.core.logger import logger
from synapr.core.models import TaskStatus
from synapr.orchestrator import SynaprOrchestrator


@click.group()
@click.version_option(version=__version__, prog_name="synapr")
def main() -> None:
    """⚡ Synapr: Autonomous Local Multi-IDE AI Orchestrator."""
    pass


@main.command()
def init() -> None:
    """Initialize a default synapr.config.json in the current workspace."""
    cfg = SynaprConfig()
    cfg.save("synapr.config.json")
    click.echo(click.style("✔ Created synapr.config.json with local air-gap defaults.", fg="green", bold=True))


@main.command()
def scan() -> None:
    """Scan and list all installed code editors and AI tools on host machine."""
    orchestrator = SynaprOrchestrator()
    editors = orchestrator.get_installed_editors()

    click.echo(click.style(f"\n🔍 Discovered {len(editors)} Code Editors on Host Machine:\n", bold=True))
    if not editors:
        click.echo(click.style("  No GUI code editors detected in standard paths or PATH.", fg="yellow"))
        click.echo("  Synapr will use CLI fallback or configured custom editors.\n")
        return

    for ed in editors:
        status = click.style("READY", fg="green") if ed.is_available else click.style("NOT FOUND", fg="red")
        ver = f" (v{ed.version})" if ed.version else ""
        click.echo(f"  • {click.style(ed.name, bold=True)}{ver}")
        click.echo(f"    ID: {ed.id} | Type: {ed.editor_type.value} | Status: [{status}]")
        click.echo(f"    Executable: {ed.executable_path}\n")


@main.command()
@click.argument("goal", required=True)
@click.option("--context", default=None, help="Additional context or path to specification file.")
def plan(goal: str, context: Optional[str]) -> None:
    """Decompose a high-level goal and run multi-LLM debate verification."""
    ctx_text = None
    if context and os.path.isfile(context):
        with open(context, "r", encoding="utf-8") as f:
            ctx_text = f.read()
    elif context:
        ctx_text = context

    orchestrator = SynaprOrchestrator()

    async def _run() -> None:
        p = await orchestrator.plan_goal(goal, ctx_text)
        click.echo(click.style(f"\n🧠 Plan Verified: {p.id} (Consensus: {p.final_consensus_score * 100:.0f}%)\n", bold=True, fg="cyan"))
        for t in p.subtasks:
            click.echo(f"  [{click.style(t.id, bold=True)}] {t.title}")
            click.echo(f"   Target Editor: {t.target_editor} | Scope: {t.file_scope}")
            click.echo(f"   Instructions: {t.instructions[:100]}...\n")

    asyncio.run(_run())


@main.command()
@click.argument("goal", required=True)
@click.option("--dry-run", is_flag=True, default=False, help="Simulate execution without spawning GUI editors.")
@click.option("--no-launch", is_flag=True, default=False, help="Provision worktrees but do not launch editor processes.")
@click.option("--context", default=None, help="Additional context or path to specification file.")
def run(goal: str, dry_run: bool, no_launch: bool, context: Optional[str]) -> None:
    """Execute end-to-end swarm loop: plan, debate, provision worktrees, and test-merge."""
    orchestrator = SynaprOrchestrator()

    async def _run() -> None:
        click.echo(click.style("\n⚡ Synapr Swarm Orchestrator Starting...", bold=True, fg="magenta"))
        summary = await orchestrator.run_goal(
            goal=goal,
            context=context,
            dry_run=dry_run,
            launch_editors=not no_launch and not dry_run,
        )
        click.echo(click.style("\n🏁 Swarm Execution Complete!", bold=True, fg="green"))
        click.echo(f"  Plan: {summary['plan_id']}")
        click.echo(f"  Tasks Completed: {summary['completed']}/{summary['total_tasks']}")
        click.echo(f"  Tasks Failed: {summary['failed']}/{summary['total_tasks']}\n")

    asyncio.run(_run())


@main.group()
def worktree() -> None:
    """Manage isolated Git worktrees."""
    pass


@worktree.command("list")
def list_wt() -> None:
    """List all Git worktrees currently provisioned by Synapr."""
    orchestrator = SynaprOrchestrator()

    async def _run() -> None:
        trees = await orchestrator.worktree_mgr.list_worktrees()
        click.echo(click.style(f"\n🌿 Active Git Worktrees ({len(trees)} total):\n", bold=True))
        for t in trees:
            click.echo(f"  • Path:   {t.get('path')}")
            click.echo(f"    Branch: {t.get('branch', 'detached')}")
            click.echo(f"    HEAD:   {t.get('head', 'unknown')}\n")

    asyncio.run(_run())


@worktree.command("clean")
@click.option("--task-id", default=None, help="Clean specific worktree by task ID.")
@click.option("--force", is_flag=True, default=True, help="Force deletion.")
def clean_wt(task_id: Optional[str], force: bool) -> None:
    """Prune and clean worktree directories."""
    orchestrator = SynaprOrchestrator()

    async def _run() -> None:
        if task_id:
            await orchestrator.worktree_mgr.cleanup_worktree(task_id, force=force)
            click.echo(click.style(f"✔ Cleaned worktree for task {task_id}", fg="green"))
        else:
            await orchestrator.worktree_mgr.prune_all()
            click.echo(click.style("✔ Pruned all stale git worktrees", fg="green"))

    asyncio.run(_run())


@main.command()
def status() -> None:
    """Show Synapr system and workspace status."""
    orchestrator = SynaprOrchestrator()

    async def _run() -> None:
        base = await orchestrator.worktree_mgr.detect_base_branch()
        wts = await orchestrator.worktree_mgr.list_worktrees()
        eds = orchestrator.get_installed_editors()
        click.echo(click.style("\n📊 Synapr Swarm Status:", bold=True))
        click.echo(f"  • Base Git Branch:     {click.style(base, bold=True, fg='cyan')}")
        click.echo(f"  • Active Worktrees:    {len(wts)}")
        click.echo(f"  • Discovered IDEs:     {len(eds)}")
        click.echo(f"  • Default LLM Engine:  {orchestrator.config.gateway.default_provider}")
        click.echo(f"  • Privacy / Air-Gap:   100% Local Guard Enabled\n")

    asyncio.run(_run())


@main.command()
@click.option("--host", default="127.0.0.1", help="Bind host address.")
@click.option("--port", default=8765, type=int, help="Port to run web dashboard on.")
@click.option("--open-browser", is_flag=True, default=True, help="Automatically open browser.")
def ui(host: str, port: int, open_browser: bool) -> None:
    """Launch the Synapr local web dashboard and control center."""
    url = f"http://{host}:{port}"
    click.echo(click.style(f"\n⚡ Synapr Dashboard starting at {url}", bold=True, fg="magenta"))
    click.echo("Press Ctrl+C to terminate.")

    if open_browser:
        # Schedule browser opening after server startup
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        def _open() -> None:
            import time
            time.sleep(1.0)
            webbrowser.open(url)

        import threading
        threading.Thread(target=_open, daemon=True).start()

    from synapr.web.app import app
    uvicorn.run(app, host=host, port=port, log_level="warning")


if __name__ == "__main__":
    main()
