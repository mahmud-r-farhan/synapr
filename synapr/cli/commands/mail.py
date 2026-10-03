"""Email triage, response drafting, and explicit dispatch commands."""

from __future__ import annotations

import json

import click

from synapr.cli.app import main


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
