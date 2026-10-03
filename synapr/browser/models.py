"""Data models for browser automation, web research, and dev-server validation."""

from __future__ import annotations

from pydantic import BaseModel, Field


class SearchResult(BaseModel):
    """Single organic search result from DuckDuckGo, SearXNG, or custom engine."""

    title: str
    url: str
    snippet: str
    source: str = "duckduckgo"


class WebPage(BaseModel):
    """Extracted content from a web page."""

    url: str
    title: str = ""
    text: str = ""
    status_code: int = 200
    content_length: int = 0
    error: str | None = None
    links: list[dict[str, str]] = Field(default_factory=list)

    @property
    def markdown(self) -> str:
        return self.text


class LocalhostValidationResult(BaseModel):
    """Result of inspecting a local development server for health and errors."""

    url: str
    reachable: bool = True
    status_code: int | None = None
    latency_ms: float = 0.0
    title: str | None = None
    has_errors: bool = False
    error_snippets: list[str] = Field(default_factory=list)
    detail: str = ""
    headers: dict[str, str] = Field(default_factory=dict)

    @property
    def is_healthy(self) -> bool:
        return self.reachable and not self.has_errors

    @property
    def errors_detected(self) -> list[str]:
        return self.error_snippets
