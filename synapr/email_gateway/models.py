"""Data models for email monitoring, triage, and draft generation."""

from __future__ import annotations

from pydantic import BaseModel, Field


class EmailMessage(BaseModel):
    """An incoming email message parsed from IMAP or local store."""

    id: str
    subject: str
    sender: str
    recipient: str = "developer@synapr.local"
    date: str
    body: str
    category: str = "general"
    priority: str = "medium"
    status: str = "unread"
    extracted_tasks: list[str] = Field(default_factory=list)

    @property
    def sender_email(self) -> str:
        return self.sender

    @property
    def received_at(self) -> str:
        return self.date


class EmailDraft(BaseModel):
    """A prepared email reply strictly isolated to the drafts folder."""

    id: str
    reply_to_id: str | None = None
    to: str
    subject: str
    body: str
    created_at: str
    status: str = "draft"
    synapr_context: str = ""

    @property
    def recipient(self) -> str:
        return self.to


class EmailTriageResult(BaseModel):
    """Categorized summary and actionable development goals from an incoming email."""

    message_id: str
    category: str
    summary: str
    actionable_items: list[str] = Field(default_factory=list)
    suggested_goal: str = ""
    priority: str = "medium"

    @property
    def urgency(self) -> str:
        return self.priority

    @property
    def executive_summary(self) -> str:
        return self.summary

    @property
    def action_items(self) -> list[str]:
        return self.actionable_items
