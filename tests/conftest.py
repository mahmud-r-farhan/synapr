"""Pytest configuration and common fixtures."""

from pathlib import Path

import pytest

from synapr.config import SynaprConfig
from synapr.orchestrator import SynaprOrchestrator


@pytest.fixture
def temp_repo(tmp_path: Path) -> Path:
    """Create a temporary initialized git repository."""
    import subprocess
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    subprocess.run(["git", "init"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_dir, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_dir, check=True)

    # Initial commit
    readme = repo_dir / "README.md"
    readme.write_text("# Test Repo\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=repo_dir, check=True)
    subprocess.run(["git", "commit", "-m", "initial commit"], cwd=repo_dir, check=True)
    return repo_dir


@pytest.fixture
def mock_orchestrator(temp_repo: Path) -> SynaprOrchestrator:
    """Return an orchestrator configured with temporary git repo and mock gateway."""
    cfg = SynaprConfig()
    cfg.gateway.default_provider = "mock"
    cfg.worktree.worktree_root = ".test_worktrees"
    return SynaprOrchestrator(config=cfg, repo_root=str(temp_repo))
