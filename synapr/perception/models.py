"""Structured results emitted by the optical perception subsystem."""

from __future__ import annotations

import time

from pydantic import BaseModel, Field


class WindowInfo(BaseModel):
    """Metadata regarding an identified GUI window."""
    handle: int
    title: str
    bounds: tuple[int, int, int, int] = (0, 0, 0, 0)  # x, y, width, height

class PerceptionResult(BaseModel):
    """Telemetry report extracted from optical window perception."""
    task_id: str
    window_found: bool = False
    window_title: str | None = None
    detected_errors: list[str] = Field(default_factory=list)
    detected_warnings: list[str] = Field(default_factory=list)
    completion_detected: bool = False
    extracted_text: str = ""
    screenshot_path: str | None = None
    timestamp: float = Field(default_factory=time.time)
