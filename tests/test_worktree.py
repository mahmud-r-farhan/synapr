"""Unit tests for Git Worktree manager."""

import asyncio
from pathlib import Path

import pytest

from synapr.config import WorktreeConfig
from synapr.core.models import TaskStatus
from synapr.worktree.manager import GitWorktreeError, WorktreeManager


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


@pytest.mark.parametrize(
    "task_id",
    ["../outside", "nested/child", "/tmp/outside", ".", "..", "task\nid", "x" * 101],
)
def test_worktree_methods_reject_unsafe_task_ids(temp_repo: Path, task_id: str) -> None:
    """Reject traversal-shaped IDs before any path or Git operation is attempted."""
    manager = WorktreeManager(str(temp_repo), WorktreeConfig(worktree_root=".test_worktrees"))

    async def _test() -> None:
        operations = (
            manager.provision_worktree(task_id),
            manager.lock_worktree(task_id),
            manager.unlock_worktree(task_id),
            manager.check_uncommitted_changes(task_id),
            manager.cleanup_worktree(task_id),
        )
        for operation in operations:
            with pytest.raises(GitWorktreeError, match="task ID"):
                await operation

    asyncio.run(_test())
    assert not (temp_repo / ".test_worktrees").exists()


def test_worktree_methods_reject_symlink_escape(temp_repo: Path, tmp_path: Path) -> None:
    """Do not let a valid task ID resolve through a symlink outside the worktree root."""
    worktree_root = temp_repo / ".test_worktrees"
    outside = tmp_path / "outside"
    worktree_root.mkdir()
    outside.mkdir()
    (outside / "keep.txt").write_text("untouched", encoding="utf-8")
    task_path = worktree_root / "task-safe"
    try:
        task_path.symlink_to(outside, target_is_directory=True)
    except (NotImplementedError, OSError) as exc:
        pytest.skip(f"Directory symlinks unavailable: {exc}")

    manager = WorktreeManager(str(temp_repo), WorktreeConfig(worktree_root=".test_worktrees"))
    with pytest.raises(GitWorktreeError, match="symlink"):
        asyncio.run(manager.cleanup_worktree("task-safe"))
    assert (outside / "keep.txt").read_text(encoding="utf-8") == "untouched"
