"""Browser, email, and GitHub integration settings."""

from pydantic import Field

from .base import _Section


class BrowserConfig(_Section):
    """Configuration for browser automation, live web research, and dev-server validation."""

    search_engine: str = Field(default="duckduckgo", description="Search engine: 'duckduckgo', 'searxng'")
    searxng_url: str = Field(default="http://localhost:8080", description="SearXNG base URL (when engine='searxng')")
    max_search_results: int = Field(default=5, ge=1, le=20, description="Max search results to retrieve")
    timeout_seconds: float = Field(default=12.0, gt=0, description="Web query timeout in seconds")
    validate_localhost_on_launch: bool = Field(default=False, description="Auto-probe dev server on task start")
    default_localhost_url: str = Field(default="http://localhost:3000", description="Default local dev URL to validate")

class EmailConfig(_Section):
    """Configuration for email monitoring, issue triage, and draft generation."""

    enabled: bool = Field(default=True, description="Enable email triage subsystem")
    imap_host: str = Field(default="", description="IMAP server hostname")
    imap_port: int = Field(default=993, ge=1, le=65535, description="IMAP port")
    imap_username: str = Field(default="", description="IMAP username / email address")
    imap_password: str | None = Field(default=None, description="IMAP password / app token")
    auto_triage: bool = Field(default=True, description="Auto-classify incoming emails into task briefs")
    save_drafts_only: bool = Field(default=True, description="Safety rule: drafts are never sent without human approval")

class GitHubConfig(_Section):
    """Configuration for GitHub repository issue sync and PR automation."""

    enabled: bool = Field(default=True, description="Enable GitHub issue integration")
    token: str | None = Field(default=None, description="GitHub personal access token")
    repository: str | None = Field(default=None, description="GitHub repository 'owner/repo' (auto-detected if None)")
    auto_link_pr: bool = Field(default=True, description="Link 'Closes #N' in generated pull requests")
    base_branch: str = Field(default="main", description="Target base branch for pull requests")
