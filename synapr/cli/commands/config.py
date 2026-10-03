"""Inspect, mutate, validate, and diagnose runtime configuration."""

from __future__ import annotations

import json
from pathlib import Path

import click

from synapr.cli.app import _service, main
from synapr.config import SynaprConfig, get_by_path, render_env_example
from synapr.core.config_service import ConfigServiceError


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
