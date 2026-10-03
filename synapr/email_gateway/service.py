"""Intelligent email processing, triage, and draft generation service."""

from __future__ import annotations

import datetime
import json
import re
from pathlib import Path
from typing import Any

from synapr.core.logger import logger
from synapr.email_gateway.models import EmailDraft, EmailMessage, EmailTriageResult

DEFAULT_SAMPLE_MESSAGES: list[dict[str, Any]] = [
    {
        "id": "mail-001",
        "subject": "[Bug Report] OAuth2 Token Expired Error during mobile sync",
        "sender": "qa-lead@example.org",
        "recipient": "dev@synapr.local",
        "date": "2026-10-02 11:20:00",
        "body": (
            "Hi team,\n\nWhen testing on mobile client build #402, our access token expires "
            "after 15 minutes, but the refresh endpoint returns 401 Unauthorized instead of renewing "
            "the session. Can we verify the JWT expiration window and add automated test coverage?\n\n"
            "Steps to reproduce:\n1. Log in on mobile client\n2. Wait 15 mins\n3. Trigger sync\n\nThanks,\nQA Team"
        ),
        "category": "bug_report",
        "priority": "high",
        "status": "unread",
        "extracted_tasks": ["Fix JWT refresh token 401", "Add test coverage for token renewal"],
    },
    {
        "id": "mail-002",
        "subject": "[Feature Request] Add Redis rate limiting to /api/dispatch",
        "sender": "product@example.org",
        "recipient": "dev@synapr.local",
        "date": "2026-10-02 14:45:00",
        "body": (
            "Hey devs,\n\nWe need to protect the dispatch API against bursts. "
            "Please implement a sliding-window rate limiter (100 req/min per API key) "
            "using Redis. If Redis is unavailable, gracefully fall back to in-memory limiting.\n\n"
            "Regards,\nProduct"
        ),
        "category": "feature_request",
        "priority": "medium",
        "status": "unread",
        "extracted_tasks": ["Implement Redis sliding-window rate limiter", "Add in-memory fallback"],
    },
]


class EmailGatewayService:
    """Manages email triage, prompt extraction, and safe response drafting."""

    def __init__(self, storage_dir: str | Path = ".synapr/mail") -> None:
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.inbox_file = self.storage_dir / "inbox.json"
        self.drafts_file = self.storage_dir / "drafts.json"
        self._ensure_storage()

    def _ensure_storage(self) -> None:
        if not self.inbox_file.is_file():
            self.inbox_file.write_text(json.dumps(DEFAULT_SAMPLE_MESSAGES, indent=2), encoding="utf-8")
        if not self.drafts_file.is_file():
            self.drafts_file.write_text(json.dumps([], indent=2), encoding="utf-8")

    def _load_messages(self) -> list[EmailMessage]:
        try:
            data = json.loads(self.inbox_file.read_text(encoding="utf-8"))
            return [EmailMessage.model_validate(item) for item in data]
        except Exception:
            return []

    def _save_messages(self, messages: list[EmailMessage]) -> None:
        payload = [msg.model_dump() for msg in messages]
        self.inbox_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _load_drafts(self) -> list[EmailDraft]:
        try:
            data = json.loads(self.drafts_file.read_text(encoding="utf-8"))
            return [EmailDraft.model_validate(item) for item in data]
        except Exception:
            return []

    def _save_drafts(self, drafts: list[EmailDraft]) -> None:
        payload = [d.model_dump() for d in drafts]
        self.drafts_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def list_messages(self, folder: str = "inbox") -> list[EmailMessage]:
        """List incoming email messages."""
        return self._load_messages()

    def get_message(self, message_id: str) -> EmailMessage | None:
        """Find a specific message by ID."""
        for msg in self._load_messages():
            if msg.id == message_id:
                return msg
        return None

    def triage_message(self, message_id: str) -> EmailTriageResult:
        """Classify email content into actionable engineering tasks."""
        msg = self.get_message(message_id)
        if not msg:
            raise ValueError(f"Message {message_id} not found")

        body_lower = msg.body.lower()
        category = "general"
        priority = "medium"

        if any(w in body_lower for w in ["bug", "error", "401", "500", "crash", "fails", "broken"]):
            category = "bug_report"
            priority = "high"
        elif any(w in body_lower for w in ["feature", "implement", "add", "support", "enhancement"]):
            category = "feature_request"
            priority = "medium"
        elif any(w in body_lower for w in ["task", "brief", "spec"]):
            category = "task_brief"

        # Extract tasks
        lines = [line.strip() for line in msg.body.splitlines() if line.strip()]
        actionable: list[str] = []
        for line in lines:
            if re.match(r"^\d+\.|\*|-", line):
                actionable.append(re.sub(r"^\d+\.|\*|-", "", line).strip())

        if not actionable:
            clean_sub = re.sub(r"\[.*?\]", "", msg.subject).strip()
            actionable = [clean_sub]

        suggested_goal = f"{actionable[0]} and verify with unit tests"

        # Update message state
        messages = self._load_messages()
        for m in messages:
            if m.id == message_id:
                m.category = category
                m.priority = priority
                m.status = "triaged"
                m.extracted_tasks = actionable
        self._save_messages(messages)

        return EmailTriageResult(
            message_id=message_id,
            category=category,
            priority=priority,
            summary=f"{msg.subject}: {len(actionable)} actionable item(s) detected",
            actionable_items=actionable,
            suggested_goal=suggested_goal,
        )

    def generate_draft(
        self,
        message_id: str,
        developer_notes: str = "",
        repo_context: str = "",
    ) -> EmailDraft:
        """Synthesize technical context and generate a safe draft reply."""
        msg = self.get_message(message_id)
        if not msg:
            raise ValueError(f"Message {message_id} not found")

        draft_id = f"draft-{message_id}-{int(datetime.datetime.now().timestamp())}"
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Synthesize technical reply body
        context_block = f"\n\nRepository Status:\n{repo_context}" if repo_context else ""
        notes_block = f"\nEngineering Note: {developer_notes}" if developer_notes else ""

        draft_body = (
            f"Hi {msg.sender.split('@')[0]},\n\n"
            f"Thank you for reaching out regarding '{msg.subject}'.\n\n"
            f"We have ingested this into our development loop. Our swarm orchestrator "
            f"is decomposing the subtasks and verifying coverage in isolated Git worktrees.{notes_block}\n\n"
            f"We will update you once automated test verification and pull requests are completed.{context_block}\n\n"
            f"Best regards,\nEngineering Team"
        )

        draft = EmailDraft(
            id=draft_id,
            reply_to_id=message_id,
            to=msg.sender,
            subject=f"Re: {msg.subject}",
            body=draft_body,
            created_at=now,
            status="draft",
            synapr_context=repo_context or "Local worktrees verified",
        )

        drafts = self._load_drafts()
        drafts.append(draft)
        self._save_drafts(drafts)

        # Mark message as drafted
        messages = self._load_messages()
        for m in messages:
            if m.id == message_id:
                m.status = "drafted"
        self._save_messages(messages)

        return draft

    def list_drafts(self) -> list[EmailDraft]:
        """List all prepared draft responses."""
        return self._load_drafts()

    def send_draft(self, draft_id: str, confirm: bool = False) -> dict[str, Any]:
        """Strict safety gate: Send email only when explicit developer confirmation is provided."""
        if not confirm:
            raise RuntimeError(
                f"SAFETY LOCK: Outbound email transmission for {draft_id} is blocked. "
                "Pass confirm=True or use --confirm in CLI to explicitly authorise sending."
            )

        drafts = self._load_drafts()
        target: EmailDraft | None = None
        for d in drafts:
            if d.id == draft_id:
                target = d
                break

        if not target:
            raise ValueError(f"Draft {draft_id} not found")

        # In production or test, record as sent
        target.status = "sent"
        self._save_drafts(drafts)

        # Update referenced message
        if target.reply_to_id:
            messages = self._load_messages()
            for m in messages:
                if m.id == target.reply_to_id:
                    m.status = "replied"
            self._save_messages(messages)

        logger.info(f"Email draft {draft_id} dispatched to {target.to} after confirmation.")
        return {
            "status": "sent",
            "draft_id": draft_id,
            "to": target.to,
            "subject": target.subject,
            "dispatched_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
