"""Pytest configuration and common fixtures."""

from collections.abc import Iterator
from pathlib import Path

import pytest

from synapr.config import ENV_VAR_SPECS, SynaprConfig
from synapr.core.config_service import ConfigService, reset_config_service, set_config_service
from synapr.orchestrator import SynaprOrchestrator

_MANAGED_ENV_NAMES = sorted({name for spec in ENV_VAR_SPECS for name in spec.names})


@pytest.fixture(autouse=True)
def isolated_environment(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Keep every test hermetic: no host env vars and no shared config service."""
    for name in _MANAGED_ENV_NAMES:
        monkeypatch.delenv(name, raising=False)
    reset_config_service()
    yield
    reset_config_service()


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


@pytest.fixture
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Chdir into an empty workspace with a dedicated configuration service."""
    monkeypatch.chdir(tmp_path)
    set_config_service(ConfigService(base_dir=tmp_path))
    yield tmp_path
    reset_config_service()


@pytest.fixture
def repo_workspace(temp_repo: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Chdir into a git repository with a dedicated configuration service."""
    monkeypatch.chdir(temp_repo)
    set_config_service(ConfigService(base_dir=temp_repo))
    yield temp_repo
    reset_config_service()
