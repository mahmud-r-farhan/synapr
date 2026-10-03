"""Unit tests for Git Worktree manager."""

import asyncio
from pathlib import Path

from synapr.config import WorktreeConfig
from synapr.core.models import TaskStatus
from synapr.worktree.manager import WorktreeManager


def test_worktree_lifecycle(temp_repo: Path) -> None:
    """Test full worktree provisioning, listing, status check, and cleanup."""
    async def _test() -> None:
        cfg = WorktreeConfig(worktree_root=".test_worktrees")
        mgr = WorktreeManager(str(temp_repo), cfg)

        # 1. Provision worktree
        instance = await mgr.provision_worktree(
            task_id="task-test-01",
            editor="vscode",
        )
        assert instance.task_id == "task-test-01"
        assert Path(instance.path).exists()
        assert instance.status == TaskStatus.PROVISIONED

        # 2. Check worktree list
        wts = await mgr.list_worktrees()
        assert len(wts) >= 2  # Main repo + new worktree

        # 3. Check uncommitted changes
        has_changes = await mgr.check_uncommitted_changes("task-test-01")
        assert has_changes is False

        # Create dummy file inside worktree
        (Path(instance.path) / "test.txt").write_text("Hello Synapr", encoding="utf-8")
        has_changes_now = await mgr.check_uncommitted_changes("task-test-01")
        assert has_changes_now is True

        # 4. Cleanup
        await mgr.cleanup_worktree("task-test-01", force=True, delete_branch=True)
        assert not Path(instance.path).exists()

    asyncio.run(_test())
