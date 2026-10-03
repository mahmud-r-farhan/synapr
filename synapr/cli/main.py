"""Click CLI interface for Synapr autonomous orchestrator."""

from __future__ import annotations

import asyncio
import json
import os
import threading
import time
import webbrowser
from pathlib import Path
from typing import Any

import click
import uvicorn

from synapr import __version__
from synapr.config import (
    SynaprConfig,
    get_by_path,
    render_env_example,
)
from synapr.core.config_service import (
    ConfigService,
    ConfigServiceError,
    get_config_service,
    set_config_service,
)
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


# --------------------------------------------------------------------------------------
# Configuration commands
# --------------------------------------------------------------------------------------


@main.group(invoke_without_command=True)
@click.pass_context
def config(ctx: click.Context) -> None:
    """Inspect and edit configuration (or use `synapr ui` to do it visually)."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@config.command("show")
@click.option("--json", "as_json", is_flag=True, default=False, help="Print raw JSON.")
@click.option("--reveal", is_flag=True, default=False, help="Show secret values in clear text.")
@click.pass_context
def config_show(ctx: click.Context, as_json: bool, reveal: bool) -> None:
    """Print the effective configuration (file + environment overrides)."""
    service = _service(ctx)
    cfg = service.config
    data = cfg.to_dict(redact=not reveal)

    if as_json:
        click.echo(json.dumps(data, indent=2))
        return

    summary = service.summary()
    click.echo(click.style("\n⚙️  Effective Synapr Configuration\n", bold=True))
    click.echo(f"  Source file: {summary['source_path'] or 'none (built-in defaults)'}")
    click.echo(f"  Writes to:   {summary['target_path']}")
    if summary["env_file"]:
        click.echo(f"  Env file:    {summary['env_file']}")
    click.echo("")

    for section, values in data.items():
        if not isinstance(values, dict):
            click.echo(f"  {click.style(section, bold=True)}: {values}")
            continue
        click.echo(click.style(f"  [{section}]", bold=True, fg="cyan"))
        for key, value in values.items():
            path = f"{section}.{key}"
            marker = ""
            if path in summary["env_overrides"]:
                marker = click.style(f"  ← {summary['env_overrides'][path]}", fg="yellow")
            click.echo(f"    {key:<28} {json.dumps(value)}{marker}")
        click.echo("")

    for error in summary["errors"]:
        click.echo(click.style(f"  ! {error}", fg="red"))


@config.command("get")
@click.argument("path")
@click.pass_context
def config_get(ctx: click.Context, path: str) -> None:
    """Read a single value, e.g. `synapr config get gateway.planner_model`."""
    try:
        value = get_by_path(_service(ctx).config, path)
    except KeyError as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(json.dumps(value))


@config.command("set")
@click.argument("path")
@click.argument("value")
@click.option("--no-save", is_flag=True, default=False, help="Change the running process only.")
@click.pass_context
def config_set(ctx: click.Context, path: str, value: str, no_save: bool) -> None:
    """Set a value, e.g. `synapr config set gateway.default_provider ollama`."""
    service = _service(ctx)
    try:
        service.set_value(path, value, persist=not no_save)
    except ConfigServiceError as exc:
        raise click.ClickException(str(exc)) from exc
    target = "memory" if no_save else str(service.target_path())
    click.echo(click.style(f"✔ {path} = {value}  (written to {target})", fg="green"))


@config.command("unset")
@click.argument("path")
@click.option("--no-save", is_flag=True, default=False, help="Change the running process only.")
@click.pass_context
def config_unset(ctx: click.Context, path: str, no_save: bool) -> None:
    """Restore a single value to its built-in default."""
    service = _service(ctx)
    try:
        default_value = get_by_path(SynaprConfig(), path)
        service.set_value(path, default_value, persist=not no_save)
    except (KeyError, ConfigServiceError) as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(click.style(f"✔ {path} restored to default ({json.dumps(default_value)})", fg="green"))


@config.command("path")
@click.pass_context
def config_path_cmd(ctx: click.Context) -> None:
    """Print the configuration file Synapr reads and writes."""
    summary = _service(ctx).summary()
    click.echo(summary["source_path"] or summary["target_path"])


@config.command("validate")
@click.pass_context
def config_validate(ctx: click.Context) -> None:
    """Validate the configuration file and report any problems."""
    service = _service(ctx)
    summary = service.summary()
    if summary["errors"]:
        for error in summary["errors"]:
            click.echo(click.style(f"✘ {error}", fg="red"))
        raise click.exceptions.Exit(1)
    click.echo(click.style("✔ Configuration is valid.", fg="green"))


@config.command("env")
@click.option("--all", "show_all", is_flag=True, default=False, help="Include variables that are unset.")
@click.option("--example", is_flag=True, default=False, help="Print a .env.example template.")
@click.option("--write-example", default=None, type=click.Path(), help="Write the template to a file.")
@click.pass_context
def config_env(ctx: click.Context, show_all: bool, example: bool, write_example: str | None) -> None:
    """List supported environment variables (and generate a .env template)."""
    if example:
        click.echo(render_env_example())
        return
    if write_example:
        Path(write_example).write_text(render_env_example(), encoding="utf-8")
        click.echo(click.style(f"✔ Wrote {write_example}", fg="green"))
        return

    report = _service(ctx).env_report()
    click.echo(click.style("\n🔐 Synapr Environment Variables\n", bold=True))
    for item in report:
        if not show_all and not item["is_set"]:
            continue
        state = click.style(f"SET via {item['set_via']}", fg="green") if item["is_set"] else click.style("unset", fg="bright_black")
        click.echo(f"  {click.style(item['name'], bold=True)}  [{state}]")
        click.echo(f"    → {item['path']} ({item['kind']}){' [secret]' if item['secret'] else ''}")
        if item["description"]:
            click.echo(f"    {item['description']}")
        click.echo("")
    if not show_all:
        click.echo("  Use --all to list every supported variable, --example for a .env template.\n")


@config.command("test")
@click.option("--provider", default=None, help="Provider to probe (defaults to the active one).")
@click.pass_context
def config_test(ctx: click.Context, provider: str | None) -> None:
    """Check that the configured LLM endpoint is reachable."""
    result = _service(ctx).test_provider(provider)
    colour = "green" if result["ok"] else "red"
    icon = "✔" if result["ok"] else "✘"
    click.echo(click.style(f"{icon} {result['provider']}: {result['detail']}", fg=colour))
    if result["models"]:
        click.echo("  Models: " + ", ".join(result["models"][:12]))


# --------------------------------------------------------------------------------------
# Web Search & Browser Research Commands (FUTURE_EXPANSIONS.md #3)
# --------------------------------------------------------------------------------------


@main.command()
@click.argument("query", required=True)
@click.option("--limit", "-n", default=5, type=int, help="Maximum number of search results (default: 5).")
@click.option(
    "--engine",
    default="duckduckgo",
    type=click.Choice(["duckduckgo", "searxng"]),
    help="Search provider.",
)
@click.option("--json", "as_json", is_flag=True, default=False, help="Output results as JSON.")
@click.pass_context
def search(ctx: click.Context, query: str, limit: int, engine: str, as_json: bool) -> None:
    """Search the web for up-to-date documentation, solutions, or live data."""
    from synapr.browser.search import search_web

    cfg = _service(ctx).config
    searxng_url = cfg.browser.searxng_url
    results = search_web(query, engine=engine, max_results=limit, searxng_url=searxng_url)

    if as_json:
        click.echo(json.dumps([r.model_dump() for r in results], indent=2))
        return

    click.echo(click.style(f"\n🌐 Search results for: '{query}' ({len(results)} found)\n", bold=True, fg="cyan"))
    if not results:
        click.echo("  No results found.")
        return

    for i, r in enumerate(results, 1):
        click.echo(f"  {click.style(str(i) + '.', bold=True)} {click.style(r.title, bold=True, fg='white')}")
        click.echo(f"     URL: {click.style(r.url, fg='bright_black')}")
        if r.snippet:
            click.echo(f"     {r.snippet}")
        click.echo("")


@main.command()
@click.argument("url", required=True)
@click.option("--max-chars", default=8000, type=int, help="Maximum characters to extract.")
@click.option("--json", "as_json", is_flag=True, default=False, help="Output as JSON.")
def fetch(url: str, max_chars: int, as_json: bool) -> None:
    """Fetch an arbitrary webpage and extract clean markdown content."""
    from synapr.browser.search import fetch_webpage

    page = fetch_webpage(url, max_chars=max_chars)
    if as_json:
        click.echo(json.dumps(page.model_dump(), indent=2))
        return

    click.echo(click.style(f"\n📄 {page.title or url}", bold=True, fg="cyan"))
    click.echo(f"  URL: {page.url} (Status: {page.status_code})")
    click.echo("=" * 60)
    click.echo(page.markdown)
    click.echo("=" * 60 + "\n")


@main.command("test-url")
@click.argument("url", default="http://localhost:3000")
@click.option("--json", "as_json", is_flag=True, default=False, help="Output as JSON.")
def test_url(url: str, as_json: bool) -> None:
    """Inspect local development server health and detect build/runtime errors."""
    from synapr.browser.engine import validate_localhost

    res = validate_localhost(url)
    if as_json:
        click.echo(json.dumps(res.model_dump(), indent=2))
        return

    icon = click.style("✔", fg="green") if res.is_healthy else click.style("✘", fg="red")
    click.echo(f"\n{icon} Dev-Server Check: {url}")
    click.echo(f"   Status Code: {res.status_code}")
    click.echo(f"   Title:       {res.title or 'N/A'}")
    click.echo(f"   Latency:     {res.latency_ms:.1f}ms")
    if res.errors_detected:
        click.echo(click.style(f"   Errors Detected ({len(res.errors_detected)}):", fg="red", bold=True))
        for err in res.errors_detected:
            click.echo(f"     • {err}")
    else:
        click.echo(click.style("   Clean runtime: No common crash banners detected.", fg="green"))
    click.echo("")


# --------------------------------------------------------------------------------------
# GitHub Issue & Worktree Lifecycle Commands (FUTURE_EXPANSIONS.md #5)
# --------------------------------------------------------------------------------------


@main.group()
def issue() -> None:
    """Manage GitHub repository issues and autonomous worktree provisioning."""


@issue.command("list")
@click.option("--state", default="open", type=click.Choice(["open", "closed", "all"]), help="Issue state.")
@click.option("--limit", default=10, type=int, help="Maximum issues to list.")
@click.option("--repo", default=None, help="Target GitHub repo (e.g. owner/repo).")
@click.option("--json", "as_json", is_flag=True, default=False, help="Output as JSON.")
def issue_list(state: str, limit: int, repo: str | None, as_json: bool) -> None:
    """List GitHub issues for the repository."""
    from synapr.github.service import GitHubIssueService

    svc = GitHubIssueService(repo_override=repo)
    issues = svc.list_issues(state=state, limit=limit)
    if as_json:
        click.echo(json.dumps([i.model_dump() for i in issues], indent=2))
        return

    click.echo(click.style(f"\n🐙 GitHub Issues ({len(issues)} found):\n", bold=True, fg="magenta"))
    if not issues:
        click.echo("  No issues found.")
        return

    for iss in issues:
        st = click.style(f"[{iss.state.upper()}]", fg="green" if iss.state == "open" else "bright_black")
        lbls = f" ({', '.join(iss.labels)})" if iss.labels else ""
        click.echo(f"  #{click.style(str(iss.number), bold=True)} {st} {iss.title}{lbls}")
        if iss.body:
            summary = iss.body.splitlines()[0][:90]
            click.echo(f"     {click.style(summary, fg='bright_black')}")
    click.echo("")


@issue.command("solve")
@click.argument("number", type=int, required=True)
@click.option("--editor", default="default", help="Target editor ID for the worktree.")
@click.option("--repo", default=None, help="Target GitHub repo.")
@click.pass_context
def issue_solve(ctx: click.Context, number: int, editor: str, repo: str | None) -> None:
    """Provision a dedicated isolated worktree and instructions for solving an issue."""
    from synapr.github.service import GitHubIssueService

    orch = _orchestrator(ctx)
    svc = GitHubIssueService(worktree_manager=orch.worktree_mgr, repo_override=repo)

    async def _solve() -> None:
        try:
            res = await svc.solve_issue_in_worktree(number, target_editor=editor)
            click.echo(click.style(f"\n✔ Worktree provisioned for Issue #{number}!", fg="green", bold=True))
            click.echo(f"   Branch:       {res['branch']}")
            click.echo(f"   Worktree Dir: {res['worktree_path']}")
            click.echo(f"   Brief:        {res.get('instructions_file') or res.get('instruction_file')}")
            click.echo("\n  Autonomous subtask prepared. Run `synapr run` or open the editor to solve.\n")
        except Exception as exc:
            raise click.ClickException(str(exc)) from exc

    asyncio.run(_solve())


@issue.command("pr")
@click.argument("number", type=int, required=True)
@click.option("--repo", default=None, help="Target GitHub repo.")
@click.option("--json", "as_json", is_flag=True, default=False, help="Output as JSON.")
def issue_pr(number: int, repo: str | None, as_json: bool) -> None:
    """Generate a clean, structured pull request description for an issue."""
    from synapr.github.service import GitHubIssueService

    svc = GitHubIssueService(repo_override=repo)
    draft = svc.prepare_pr_for_issue(number)
    if as_json:
        click.echo(json.dumps(draft.model_dump(), indent=2))
        return

    click.echo(click.style(f"\n📦 Pull Request Draft for Issue #{number}\n", bold=True, fg="cyan"))
    click.echo(f"Title:  {draft.title}")
    click.echo(f"Branch: {draft.head_branch} -> {draft.base_branch}")
    click.echo("-" * 60)
    click.echo(draft.body)
    click.echo("-" * 60 + "\n")


# --------------------------------------------------------------------------------------
# Email Gateway & Safe Drafting Commands (FUTURE_EXPANSIONS.md #4)
# --------------------------------------------------------------------------------------


@main.group()
def mail() -> None:
    """Triage incoming emails and generate context-aware response drafts safely."""


@mail.command("list")
@click.option("--folder", default="inbox", help="Mailbox folder (default: inbox).")
@click.option("--json", "as_json", is_flag=True, default=False, help="Output as JSON.")
def mail_list(folder: str, as_json: bool) -> None:
    """List incoming engineering and client messages."""
    from synapr.email_gateway.service import EmailGatewayService

    svc = EmailGatewayService()
    msgs = svc.list_messages(folder=folder)
    if as_json:
        click.echo(json.dumps([m.model_dump() for m in msgs], indent=2))
        return

    click.echo(click.style(f"\n✉️  Messages in [{folder}] ({len(msgs)} total):\n", bold=True, fg="yellow"))
    if not msgs:
        click.echo("  No messages in folder.")
        return

    for m in msgs:
        click.echo(f"  [{click.style(m.id, bold=True)}] From: {m.sender} <{m.sender_email}>")
        click.echo(f"   Subject: {click.style(m.subject, bold=True)}")
        click.echo(f"   Date:    {m.received_at}")
        snippet = m.body.splitlines()[0][:80] if m.body else ""
        click.echo(f"   Preview: {click.style(snippet, fg='bright_black')}\n")


@mail.command("triage")
@click.argument("message_id", required=True)
@click.option("--json", "as_json", is_flag=True, default=False, help="Output as JSON.")
def mail_triage(message_id: str, as_json: bool) -> None:
    """Analyze and triage an email into priority, category, and action items."""
    from synapr.email_gateway.service import EmailGatewayService

    svc = EmailGatewayService()
    try:
        triage = svc.triage_message(message_id)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc

    if as_json:
        click.echo(json.dumps(triage.model_dump(), indent=2))
        return

    click.echo(click.style(f"\n📋 Triage Analysis for {message_id}\n", bold=True, fg="cyan"))
    click.echo(f"  Category: {triage.category.upper()} | Priority: {click.style(triage.urgency.upper(), bold=True)}")
    click.echo(f"  Summary:  {triage.executive_summary}")
    if triage.action_items:
        click.echo(click.style("\n  Action Items:", bold=True))
        for item in triage.action_items:
            click.echo(f"    • {item}")
    click.echo("")


@mail.command("draft")
@click.argument("message_id", required=True)
@click.option("--notes", default="", help="Developer notes or technical solution constraints.")
@click.option("--json", "as_json", is_flag=True, default=False, help="Output as JSON.")
def mail_draft(message_id: str, notes: str, as_json: bool) -> None:
    """Generate a high-quality technical response draft saved to Drafts."""
    from synapr.email_gateway.service import EmailGatewayService

    svc = EmailGatewayService()
    try:
        draft = svc.generate_draft(message_id, developer_notes=notes)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc

    if as_json:
        click.echo(json.dumps(draft.model_dump(), indent=2))
        return

    click.echo(click.style(f"\n📝 Created Draft [{draft.id}] for {draft.recipient}\n", bold=True, fg="green"))
    click.echo(f"Subject: {draft.subject}")
    click.echo(f"Status:  {draft.status} (Safety Lock: Active)")
    click.echo("-" * 60)
    click.echo(draft.body)
    click.echo("-" * 60)
    click.echo(f"  To send this draft, run: synapr mail send {draft.id} --confirm\n")


@mail.command("send")
@click.argument("draft_id", required=True)
@click.option("--confirm", is_flag=True, default=False, help="Confirm dispatch (safety lock).")
def mail_send(draft_id: str, confirm: bool) -> None:
    """Safely dispatch an approved email draft (requires --confirm flag)."""
    from synapr.email_gateway.service import EmailGatewayService

    svc = EmailGatewayService()
    try:
        res = svc.send_draft(draft_id, confirm=confirm)
        target = res.get("recipient") or res.get("to")
        sent_time = res.get("sent_at") or res.get("dispatched_at")
        click.echo(click.style(f"\n✔ Email {draft_id} safely sent to {target}!", fg="green", bold=True))
        click.echo(f"   Archived in sent mailbox at {sent_time}\n")
    except RuntimeError as exc:
        click.echo(click.style(f"\n🔒 Safety Lock: {exc}", fg="yellow", bold=True))
        click.echo("   Run again with --confirm to authorize dispatch.\n")
        raise click.exceptions.Exit(1) from exc
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc


# --------------------------------------------------------------------------------------
# Dashboard
# --------------------------------------------------------------------------------------


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


if __name__ == "__main__":
    main()
