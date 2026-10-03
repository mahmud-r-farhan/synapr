"""Tests for web API endpoints: Web Search, Fetch URL, Dev-Server probe, GitHub issues, and Email Hub."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from starlette.testclient import TestClient

from synapr.browser.models import LocalhostValidationResult, SearchResult, WebPage
from synapr.github.models import GitHubIssue, GitHubPRDraft
from synapr.web.app import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_api_search_get(client: TestClient) -> None:
    fake_results = [
        SearchResult(title="Python Official", url="https://python.org", snippet="Python language"),
    ]
    with patch("synapr.browser.search.search_web", return_value=fake_results):
        resp = client.get("/api/search?q=python&limit=3")
        assert resp.status_code == 200
        data = resp.json()
        assert data["query"] == "python"
        assert len(data["results"]) == 1
        assert data["results"][0]["title"] == "Python Official"


def test_api_fetch_url(client: TestClient) -> None:
    fake_page = WebPage(
        url="https://docs.python.org",
        title="Python Docs",
        text="# Documentation",
        status_code=200,
    )
    with patch("synapr.browser.search.fetch_webpage", return_value=fake_page):
        resp = client.post("/api/fetch-url", json={"url": "https://docs.python.org"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Python Docs"
        assert "# Documentation" in data["markdown"] or "# Documentation" in data["text"]


def test_api_validate_localhost(client: TestClient) -> None:
    fake_diag = LocalhostValidationResult(
        url="http://localhost:3000",
        reachable=True,
        status_code=200,
        latency_ms=15.0,
        title="React App",
        has_errors=False,
        error_snippets=[],
    )
    with patch("synapr.browser.engine.validate_localhost", return_value=fake_diag):
        resp = client.post("/api/browser/validate-localhost", json={"url": "http://localhost:3000"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_healthy"] is True
        assert data["title"] == "React App"


def test_api_github_issues(client: TestClient) -> None:
    fake_issue = GitHubIssue(
        number=1,
        title="Initial Setup",
        body="Set up project scaffolding",
        state="open",
        author="mahmud",
        labels=["setup"],
    )
    with patch("synapr.github.service.GitHubIssueService.list_issues", return_value=[fake_issue]):
        resp = client.get("/api/github/issues?state=open")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["number"] == 1
        assert data[0]["title"] == "Initial Setup"


def test_api_github_issue_detail_and_pr(client: TestClient) -> None:
    fake_issue = GitHubIssue(
        number=5,
        title="Telemetry bug",
        body="Fix SSE timeout",
        state="open",
        author="alice",
        labels=["bug"],
    )
    fake_pr = GitHubPRDraft(
        issue_number=5,
        title="Fix #5: Telemetry bug",
        branch="fix/issue-5-telemetry-bug",
        base="main",
        body="Closes #5",
    )
    with patch("synapr.github.service.GitHubIssueService.get_issue", return_value=fake_issue), \
         patch("synapr.github.service.GitHubIssueService.prepare_pr_for_issue", return_value=fake_pr):
        resp = client.get("/api/github/issues/5")
        assert resp.status_code == 200
        assert resp.json()["title"] == "Telemetry bug"

        pr_resp = client.get("/api/github/issues/5/pr")
        assert pr_resp.status_code == 200
        assert pr_resp.json()["title"] == "Fix #5: Telemetry bug"


def test_api_mail_endpoints(client: TestClient) -> None:
    # 1. List inbox messages
    resp = client.get("/api/mail/messages?folder=inbox")
    assert resp.status_code == 200
    msgs = resp.json()
    assert len(msgs) >= 1
    msg_id = msgs[0]["id"]

    # 2. Get message by id
    detail_resp = client.get(f"/api/mail/messages/{msg_id}")
    assert detail_resp.status_code == 200
    assert detail_resp.json()["id"] == msg_id

    # 3. Triage message
    triage_resp = client.post(f"/api/mail/messages/{msg_id}/triage")
    assert triage_resp.status_code == 200
    triage_data = triage_resp.json()
    assert "urgency" in triage_data or "priority" in triage_data
    assert "action_items" in triage_data or "actionable_items" in triage_data

    # 4. Generate draft
    draft_resp = client.post(
        f"/api/mail/messages/{msg_id}/draft",
        json={"developer_notes": "Will test thoroughly"},
    )
    assert draft_resp.status_code == 200
    draft_data = draft_resp.json()
    draft_id = draft_data["id"]
    assert "Will test thoroughly" in draft_data["body"]

    # 5. Send draft without confirmation -> 403 Forbidden (Safety lock)
    unconfirmed = client.post(f"/api/mail/drafts/{draft_id}/send", json={"confirm": False})
    assert unconfirmed.status_code == 403

    # 6. Send draft with confirmation -> 200 OK
    confirmed = client.post(f"/api/mail/drafts/{draft_id}/send", json={"confirm": True})
    assert confirmed.status_code == 200
    assert confirmed.json()["status"] == "sent"
