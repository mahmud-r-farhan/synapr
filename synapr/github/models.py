"""Data models for GitHub issue and pull request orchestration."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class GitHubIssue(BaseModel):
    """Structured representation of a GitHub issue."""

    number: int
    title: str
    body: str
    state: str = "open"
    author: str = ""
    labels: list[str] = Field(default_factory=list)
    html_url: str = ""
    created_at: str = ""
    comments_count: int = 0


class GitHubPRDraft(BaseModel):
    """Pull request description linking resolved issues and test results."""

    issue_number: int = 0
    title: str
    branch: str = ""
    base: str = "main"
    body: str
    closes_issue: bool = True

    def __init__(self, **data: Any) -> None:
        if "head_branch" in data and "branch" not in data:
            data["branch"] = data.pop("head_branch")
        if "base_branch" in data and "base" not in data:
            data["base"] = data.pop("base_branch")
        super().__init__(**data)

    @property
    def head_branch(self) -> str:
        return self.branch

    @property
    def base_branch(self) -> str:
        return self.base
