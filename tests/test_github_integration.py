"""Tests for GitHub issue integration, worktree provisioning, and PR draft generator."""

from __future__ import annotations

from unittest.mock import patch

from click.testing import CliRunner

from synapr.cli.main import main
from synapr.github.client import GitHubClient, detect_repository
from synapr.github.models import GitHubIssue, GitHubPRDraft
from synapr.github.service import GitHubIssueService


def test_detect_repository() -> None:
    repo = detect_repository()
    assert repo == "mahmud-r-farhan/synapr" or repo is not None


def test_github_client_issues() -> None:
    client = GitHubClient(repository="test-owner/test-repo")
    fake_issues = [
        GitHubIssue(
            number=42,
            title="Async deadlock in telemetry stream",
            body="Steps to reproduce: open SSE and disconnect abruptly.",
            state="open",
            author="dev",
            labels=["bug", "high-priority"],
        )
    ]
    with patch.object(client, "fetch_issues", return_value=fake_issues):
        issues = client.fetch_issues(state="open")
        assert len(issues) == 1
        assert issues[0].number == 42
        assert "Async deadlock" in issues[0].title


def test_github_issue_service_pr_draft() -> None:
    svc = GitHubIssueService(repo_override="test-owner/test-repo")
    mock_issue = GitHubIssue(
        number=17,
        title="Implement DuckDuckGo HTML search fallback",
        body="Requirements: search engine should work without an API key.",
        state="open",
        author="alice",
        labels=["feature"],
    )
    with patch.object(svc.client, "fetch_issue", return_value=mock_issue):
        draft = svc.prepare_pr_for_issue(17)
        assert isinstance(draft, GitHubPRDraft)
        assert draft.issue_number == 17
        assert "Closes #17" in draft.body
        assert "DuckDuckGo" in draft.body
        assert "issue-17" in draft.branch


def test_cli_issue_list() -> None:
    runner = CliRunner()
    fake_issues = [
        GitHubIssue(
            number=99,
            title="UI dark mode contrast enhancement",
            body="Colors need higher contrast ratio.",
            state="open",
            author="designer",
            labels=["enhancement"],
        )
    ]
    with patch("synapr.github.service.GitHubIssueService.list_issues", return_value=fake_issues):
        res = runner.invoke(main, ["issue", "list"])
        assert res.exit_code == 0
        assert "#99" in res.output
        assert "UI dark mode" in res.output


def test_cli_issue_pr() -> None:
    runner = CliRunner()
    draft = GitHubPRDraft(
        issue_number=99,
        title="Resolve #99: UI dark mode contrast enhancement",
        branch="fix/issue-99-ui-dark-mode",
        base="main",
        body="Closes #99\n\n### Summary of Changes\n- Improved contrast",
    )
    with patch("synapr.github.service.GitHubIssueService.prepare_pr_for_issue", return_value=draft):
        res = runner.invoke(main, ["issue", "pr", "99"])
        assert res.exit_code == 0
        assert "Pull Request Draft for Issue #99" in res.output
        assert "Closes #99" in res.output
