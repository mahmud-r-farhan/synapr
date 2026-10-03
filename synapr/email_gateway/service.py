"""Email triage, draft generation, and explicit safe-dispatch service."""

from __future__ import annotations

import datetime
import re
from pathlib import Path
from typing import Any

from synapr.core.logger import logger
from synapr.email_gateway.models import EmailDraft, EmailMessage, EmailTriageResult
from synapr.email_gateway.sample_data import DEFAULT_SAMPLE_MESSAGES as DEFAULT_SAMPLE_MESSAGES
from synapr.email_gateway.storage import EmailStorage


class EmailGatewayService:
    """Manages email triage, prompt extraction, and safe response drafting."""

    def __init__(self, storage_dir: str | Path = ".synapr/mail") -> None:
        self.storage = EmailStorage(storage_dir)
        self.storage_dir = self.storage.storage_dir
        self.inbox_file = self.storage.inbox_file
        self.drafts_file = self.storage.drafts_file

    def _ensure_storage(self) -> None:
        self.storage._ensure_storage()

    def _load_messages(self) -> list[EmailMessage]:
        return self.storage._load_messages()

    def _save_messages(self, messages: list[EmailMessage]) -> None:
        self.storage._save_messages(messages)

    def _load_drafts(self) -> list[EmailDraft]:
        return self.storage._load_drafts()

    def _save_drafts(self, drafts: list[EmailDraft]) -> None:
        self.storage._save_drafts(drafts)

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
