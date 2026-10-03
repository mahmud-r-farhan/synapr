"""Local JSON persistence for email messages and safe drafts."""

from __future__ import annotations

import json
from pathlib import Path

from synapr.email_gateway.models import EmailDraft, EmailMessage
from synapr.email_gateway.sample_data import DEFAULT_SAMPLE_MESSAGES


class EmailStorage:
    """Read and write the local inbox and drafts files."""

    def __init__(self, storage_dir: str | Path) -> None:
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
