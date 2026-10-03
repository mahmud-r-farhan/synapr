"""Tests for email gateway, triage, safe draft generation, and safety dispatch gate."""

from __future__ import annotations

import pytest
from click.testing import CliRunner

from synapr.cli.main import main
from synapr.email_gateway.models import EmailDraft, EmailTriageResult
from synapr.email_gateway.service import EmailGatewayService


def test_email_service_initialization(tmp_path) -> None:
    svc = EmailGatewayService(storage_dir=tmp_path / "mail")
    inbox = svc.list_messages("inbox")
    assert len(inbox) >= 1
    assert inbox[0].id == "mail-001"
    assert "OAuth2" in inbox[0].subject


def test_email_triage(tmp_path) -> None:
    svc = EmailGatewayService(storage_dir=tmp_path / "mail")
    triage = svc.triage_message("mail-001")
    assert isinstance(triage, EmailTriageResult)
    assert triage.category == "bug_report"
    assert triage.urgency in {"high", "critical"}
    assert triage.priority in {"high", "critical"}
    assert len(triage.action_items) > 0


def test_email_draft_creation(tmp_path) -> None:
    svc = EmailGatewayService(storage_dir=tmp_path / "mail")
    draft = svc.generate_draft("mail-001", developer_notes="Fixed in PR #42.")
    assert isinstance(draft, EmailDraft)
    assert draft.status == "draft"
    assert "PR #42" in draft.body
    assert draft.recipient == "qa-lead@example.org"
    assert draft.to == "qa-lead@example.org"

    drafts = svc.list_drafts()
    assert any(d.id == draft.id for d in drafts)


def test_email_safety_gate_lock(tmp_path) -> None:
    svc = EmailGatewayService(storage_dir=tmp_path / "mail")
    draft = svc.generate_draft("mail-001")

    # Safety lock: Must raise RuntimeError if confirm is False
    with pytest.raises(RuntimeError, match="SAFETY LOCK"):
        svc.send_draft(draft.id, confirm=False)

    # With confirmation, it succeeds
    result = svc.send_draft(draft.id, confirm=True)
    assert result["status"] == "sent"
    assert result["to"] == "qa-lead@example.org"

    # Draft should now be recorded as sent
    drafts = svc.list_drafts()
    matching = [d for d in drafts if d.id == draft.id]
    assert len(matching) == 1
    assert matching[0].status == "sent"


def test_cli_mail_list(tmp_path, monkeypatch) -> None:
    svc = EmailGatewayService(storage_dir=tmp_path / "mail")
    monkeypatch.setattr("synapr.email_gateway.service.EmailGatewayService", lambda: svc)

    runner = CliRunner()
    result = runner.invoke(main, ["mail", "list"])
    assert result.exit_code == 0
    assert "Messages in [inbox]" in result.output
    assert "mail-001" in result.output


def test_cli_mail_triage(tmp_path, monkeypatch) -> None:
    svc = EmailGatewayService(storage_dir=tmp_path / "mail")
    monkeypatch.setattr("synapr.email_gateway.service.EmailGatewayService", lambda: svc)

    runner = CliRunner()
    result = runner.invoke(main, ["mail", "triage", "mail-001"])
    assert result.exit_code == 0
    assert "Triage Analysis for mail-001" in result.output
    assert "Category:" in result.output


def test_cli_mail_draft_and_send_safety_gate(tmp_path, monkeypatch) -> None:
    svc = EmailGatewayService(storage_dir=tmp_path / "mail")
    monkeypatch.setattr("synapr.email_gateway.service.EmailGatewayService", lambda: svc)

    runner = CliRunner()
    draft_res = runner.invoke(main, ["mail", "draft", "mail-001", "--notes", "Patch applied"])
    assert draft_res.exit_code == 0
    assert "Created Draft" in draft_res.output

    # Find the draft id
    drafts = svc.list_drafts()
    assert len(drafts) == 1
    draft_id = drafts[0].id

    # Attempt send without --confirm -> should trigger safety exit
    unconfirmed = runner.invoke(main, ["mail", "send", draft_id])
    assert unconfirmed.exit_code != 0
    assert "Safety Lock" in unconfirmed.output

    # Send with --confirm -> should succeed
    confirmed = runner.invoke(main, ["mail", "send", draft_id, "--confirm"])
    assert confirmed.exit_code == 0
    assert "safely sent" in confirmed.output
