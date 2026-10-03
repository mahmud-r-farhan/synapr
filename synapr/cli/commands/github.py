"""GitHub issue listing, worktree provisioning, and PR draft commands."""

from __future__ import annotations

import asyncio
import json

import click

from synapr.cli.app import _orchestrator, main


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
