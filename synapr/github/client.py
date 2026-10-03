"""GitHub API and CLI connector with zero-token public fallback and offline caching."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from synapr.core.http import validate_url
from synapr.core.logger import logger
from synapr.github.models import GitHubIssue

MOCK_REPO_ISSUES: list[dict[str, Any]] = [
    {
        "number": 101,
        "title": "Add token bucket rate-limiter to API gateway",
        "body": (
            "### Description\n"
            "The `/api/execute` endpoint currently accepts an unbounded rate of requests.\n\n"
            "### Requirements\n"
            "- Implement sliding window or token bucket limiter (default: 60 rpm)\n"
            "- Add HTTP 429 Too Many Requests response with Retry-After header\n"
            "- Unit tests covering burst traffic scenarios\n"
        ),
        "state": "open",
        "author": "mahmud-r-farhan",
        "labels": ["enhancement", "api", "synapr-managed"],
        "html_url": "https://github.com/mahmud-r-farhan/synapr/issues/101",
        "created_at": "2026-10-01T10:00:00Z",
        "comments_count": 2,
    },
    {
        "number": 102,
        "title": "Support Neovim remote socket client dispatch in worktrees",
        "body": (
            "### Feature Request\n"
            "When running headless on Linux, dispatching Neovim via `--listen /tmp/nvim.sock` "
            "allows headless programmatic buffer manipulation.\n\n"
            "### Acceptance Criteria\n"
            "- Add `neovim` to editor registry with `--listen` argument formatting\n"
            "- Test discovery on PATH for `nvim`\n"
        ),
        "state": "open",
        "author": "dev-contributor",
        "labels": ["editor", "neovim", "good first issue"],
        "html_url": "https://github.com/mahmud-r-farhan/synapr/issues/102",
        "created_at": "2026-10-02T15:30:00Z",
        "comments_count": 1,
    },
]


def detect_repository(repo_root: str | Path = ".") -> str:
    """Detect 'owner/repo' from git origin remote, or return default."""
    try:
        cmd = ["git", "remote", "get-url", "origin"]
        out = subprocess.check_output(cmd, cwd=str(repo_root), stderr=subprocess.DEVNULL).decode("utf-8").strip()
        # Parse git@github.com:owner/repo.git or https://github.com/owner/repo(.git)
        match = re.search(r"github\.com[:/]([^/]+/[^/.]+)", out)
        if match:
            return match.group(1).rstrip(".git")
    except Exception:
        pass
    return "mahmud-r-farhan/synapr"


class GitHubClient:
    """Connects to GitHub via gh CLI or REST API."""

    def __init__(
        self,
        repository: str | None = None,
        token: str | None = None,
        cache_dir: str | Path = ".synapr/github",
    ) -> None:
        self.repository = repository or detect_repository()
        self.token = token or os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._cache_file = self.cache_dir / "issues_cache.json"

    def fetch_issues(self, state: str = "open", limit: int = 15) -> list[GitHubIssue]:
        """Fetch issues using gh CLI, then REST API, with resilient offline caching."""
        # 1. Try gh CLI if available
        if shutil.which("gh"):
            try:
                cmd = [
                    "gh",
                    "issue",
                    "list",
                    "--repo",
                    self.repository,
                    "--state",
                    state,
                    "--limit",
                    str(limit),
                    "--json",
                    "number,title,body,state,author,labels,url,createdAt,comments",
                ]
                out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL).decode("utf-8")
                raw_items = json.loads(out)
                issues = [
                    GitHubIssue(
                        number=item["number"],
                        title=item["title"],
                        body=item.get("body", ""),
                        state=item.get("state", "open").lower(),
                        author=(item.get("author") or {}).get("login", ""),
                        labels=[lbl["name"] for lbl in item.get("labels", []) if isinstance(lbl, dict)],
                        html_url=item.get("url", ""),
                        created_at=item.get("createdAt", ""),
                        comments_count=len(item.get("comments", [])),
                    )
                    for item in raw_items
                ]
                if issues:
                    self._write_cache(issues)
                    return issues
            except Exception as exc:
                logger.debug(f"gh CLI issue list failed: {exc}")

        # 2. Try GitHub REST API
        try:
            url = f"https://api.github.com/repos/{self.repository}/issues?state={state}&per_page={limit}"
            headers = {
                "User-Agent": "Synapr-Swarm-Orchestrator/0.1.0",
                "Accept": "application/vnd.github.v3+json",
            }
            if self.token:
                headers["Authorization"] = f"Bearer {self.token}"

            validate_url(url)
            req = urllib.request.Request(url, headers=headers)
            # validate_url() restricts this outbound request to HTTP(S).
            with urllib.request.urlopen(req, timeout=8.0) as resp:  # nosec B310
                data = json.loads(resp.read().decode("utf-8", errors="replace"))

            issues = []
            for item in data:
                # Exclude pull requests (GitHub issues API includes PRs with 'pull_request' key)
                if "pull_request" in item:
                    continue
                issues.append(
                    GitHubIssue(
                        number=item["number"],
                        title=item["title"],
                        body=item.get("body") or "",
                        state=item.get("state", "open").lower(),
                        author=(item.get("user") or {}).get("login", ""),
                        labels=[lbl["name"] for lbl in item.get("labels", []) if isinstance(lbl, dict)],
                        html_url=item.get("html_url", ""),
                        created_at=item.get("created_at", ""),
                        comments_count=item.get("comments", 0),
                    )
                )
            if issues:
                self._write_cache(issues)
                return issues
        except Exception as exc:
            logger.debug(f"GitHub REST API fetch failed ({exc}), falling back to local cache/mock")

        # 3. Fallback: local cached issues or mock issues
        return self._read_cache_or_defaults()

    def fetch_issue(self, number: int) -> GitHubIssue | None:
        """Fetch a specific issue by number."""
        for issue in self.fetch_issues(state="all", limit=50):
            if issue.number == number:
                return issue
        return None

    def _write_cache(self, issues: list[GitHubIssue]) -> None:
        try:
            payload = [i.model_dump() for i in issues]
            self._cache_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except Exception:
            pass

    def _read_cache_or_defaults(self) -> list[GitHubIssue]:
        if self._cache_file.is_file():
            try:
                data = json.loads(self._cache_file.read_text(encoding="utf-8"))
                return [GitHubIssue.model_validate(item) for item in data]
            except Exception:
                pass
        return [GitHubIssue.model_validate(item) for item in MOCK_REPO_ISSUES]
