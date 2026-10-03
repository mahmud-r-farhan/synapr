"""GitHub issue lifecycle and worktree orchestration subsystem."""

from synapr.github.client import GitHubClient, detect_repository
from synapr.github.models import GitHubIssue, GitHubPRDraft
from synapr.github.service import GitHubIssueService

__all__ = [
    "GitHubClient",
    "GitHubIssue",
    "GitHubIssueService",
    "GitHubPRDraft",
    "detect_repository",
]
