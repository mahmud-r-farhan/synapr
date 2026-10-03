"""Core planning, execution, worktree, and status commands."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import click

from synapr.cli.app import _orchestrator, _service, main
from synapr.config import SynaprConfig, render_env_example
from synapr.orchestrator import SynaprOrchestrator


@main.command()
@click.option("--force", is_flag=True, default=False, help="Overwrite an existing config file.")
@click.option("--provider", default=None, help="Pre-select an LLM provider (e.g. ollama).")
@click.option(
    "--output", default="synapr.config.json", show_default=True, help="Destination config file."
)
@click.option(
    "--with-env-example/--no-env-example",
    default=True,
    show_default=True,
    help="Also write a documented .env.example next to the config.",
)
def init(force: bool, provider: str | None, output: str, with_env_example: bool) -> None:
    """Initialize a default synapr.config.json in the current workspace."""
    target = Path(output)
    if target.exists() and not force:
        raise click.ClickException(f"{target} already exists. Re-run with --force to overwrite.")

    cfg = SynaprConfig()
    if provider:
        cfg.gateway.default_provider = provider
    cfg.save(target)
    click.echo(click.style(f"✔ Created {target} with local air-gap defaults.", fg="green", bold=True))

    if with_env_example:
        example = target.parent / ".env.example"
        example.write_text(render_env_example(), encoding="utf-8")
        click.echo(click.style(f"✔ Wrote {example} documenting every environment variable.", fg="green"))

    click.echo("  Tip: run `synapr ui` and open the Configuration tab to edit everything visually.")


@main.command()
@click.pass_context
def scan(ctx: click.Context) -> None:
    """Scan and list all installed code editors and AI tools on host machine."""
    orchestrator = _orchestrator(ctx)
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
@click.pass_context
def plan(ctx: click.Context, goal: str, context: str | None) -> None:
    """Decompose a high-level goal and run multi-LLM debate verification."""
    ctx_text = None
    if context and os.path.isfile(context):
        with open(context, encoding="utf-8") as f:
            ctx_text = f.read()
    elif context:
        ctx_text = context

    orchestrator = _orchestrator(ctx)

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
@click.pass_context
def run(ctx: click.Context, goal: str, dry_run: bool, no_launch: bool, context: str | None) -> None:
    """Execute end-to-end swarm loop: plan, debate, provision worktrees, and test-merge."""
    orchestrator = _orchestrator(ctx)

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


@worktree.command("list")
@click.pass_context
def list_wt(ctx: click.Context) -> None:
    """List all Git worktrees currently provisioned by Synapr."""
    orchestrator = _orchestrator(ctx)

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
@click.pass_context
def clean_wt(ctx: click.Context, task_id: str | None, force: bool) -> None:
    """Prune and clean worktree directories."""
    orchestrator = _orchestrator(ctx)

    async def _run() -> None:
        if task_id:
            await orchestrator.worktree_mgr.cleanup_worktree(task_id, force=force)
            click.echo(click.style(f"✔ Cleaned worktree for task {task_id}", fg="green"))
        else:
            await orchestrator.worktree_mgr.prune_all()
            click.echo(click.style("✔ Pruned all stale git worktrees", fg="green"))

    asyncio.run(_run())


@main.command()
@click.pass_context
def status(ctx: click.Context) -> None:
    """Show Synapr system and workspace status."""
    service = _service(ctx)
    orchestrator = SynaprOrchestrator(config=service.config)
    summary = service.summary()

    async def _run() -> None:
        base = await orchestrator.worktree_mgr.detect_base_branch()
        wts = await orchestrator.worktree_mgr.list_worktrees()
        eds = orchestrator.get_installed_editors()
        click.echo(click.style("\n📊 Synapr Swarm Status:", bold=True))
        click.echo(f"  • Base Git Branch:     {click.style(base, bold=True, fg='cyan')}")
        click.echo(f"  • Active Worktrees:    {len(wts)}")
        click.echo(f"  • Discovered IDEs:     {len(eds)}")
        click.echo(f"  • Default LLM Engine:  {orchestrator.config.gateway.default_provider}")
        click.echo(f"  • Config File:         {summary['source_path'] or 'defaults (none on disk)'}")
        click.echo(f"  • Env Overrides:       {len(summary['env_overrides'])}")
        privacy = "100% Local Guard Enabled" if summary["local_only"] else "Remote provider active"
        click.echo(f"  • Privacy / Air-Gap:   {privacy}\n")

    asyncio.run(_run())
