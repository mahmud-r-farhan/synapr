"""Web search, page-fetch, and local development server commands."""

from __future__ import annotations

import json

import click

from synapr.cli.app import _service, main


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
