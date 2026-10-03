"""Validated request models for the dashboard API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class GoalRequest(BaseModel):
    goal: str
    context: str | None = None
    dry_run: bool = False
    launch_editors: bool = True

class WorktreeActionRequest(BaseModel):
    task_id: str | None = None
    force: bool = True
    delete_branch: bool = False

class ConfigUpdateRequest(BaseModel):
    """Partial configuration payload merged into the active configuration."""

    config: dict[str, Any] = Field(default_factory=dict)
    persist: bool = True

class ConfigValueRequest(BaseModel):
    """Single dotted-path assignment (``gateway.planner_model``)."""

    path: str
    value: Any = None
    persist: bool = True

class EnvUpdateRequest(BaseModel):
    """Runtime environment variable declaration, optionally stored in ``.env``."""

    values: dict[str, str] = Field(default_factory=dict)
    unset: list[str] = Field(default_factory=list)
    persist: bool = False
    env_file: str = ".env"

class ProviderTestRequest(BaseModel):
    provider: str | None = None

class SearchRequest(BaseModel):
    query: str
    limit: int = 5
    fetch_content: bool = True

class FetchUrlRequest(BaseModel):
    url: str
    max_chars: int = 12000

class LocalhostValidateRequest(BaseModel):
    url: str = "http://localhost:3000"

class EmailDraftRequest(BaseModel):
    developer_notes: str = ""

class EmailSendRequest(BaseModel):
    confirm: bool = False
