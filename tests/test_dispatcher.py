"""Unit tests for task dispatcher and instruction injection."""

import asyncio
from pathlib import Path
from synapr.core.models import SubTask, TaskStatus, WorktreeInstance
from synapr.dispatcher.bridge import TaskDispatcher


def test_instruction_injection(tmp_path: Path) -> None:
    """Test generating AGENT_INSTRUCTIONS.md, .cursorrules, and .vscode/settings.json."""
    dispatcher = TaskDispatcher()
    task = SubTask(
        id="task-auth-01",
        title="JWT Auth",
        description="Implement JWT tokens",
        target_editor="vscode",
        file_scope=["src/auth/*"],
        instructions="Use RS256 algorithm.",
        test_command="pytest tests/test_auth.py",
    )

    worktree_dir = tmp_path / "worktree"
    worktree_dir.mkdir()

    dispatcher.inject_task_context(str(worktree_dir), task)

    # Verify injected files
    assert (worktree_dir / "AGENT_INSTRUCTIONS.md").exists()
    assert (worktree_dir / ".synapr_task.json").exists()
    assert (worktree_dir / ".cursorrules").exists()
    assert (worktree_dir / ".vscode" / "settings.json").exists()

    content = (worktree_dir / "AGENT_INSTRUCTIONS.md").read_text(encoding="utf-8")
    assert "JWT Auth" in content
    assert "RS256" in content


def test_launch_editor_dry_run(tmp_path: Path) -> None:
    """Test simulated dry-run launch."""
    async def _test() -> None:
        dispatcher = TaskDispatcher()
        task = SubTask(
            id="task-dry-01",
            title="Dry Run",
            description="Testing launcher",
            target_editor="vscode",
        )
        worktree_dir = tmp_path / "wt_dry"
        worktree_dir.mkdir()

        wt = WorktreeInstance(
            task_id=task.id,
            branch="synapr/dry-01",
            path=str(worktree_dir),
            editor="vscode",
        )

        pid = await dispatcher.launch_editor(wt, task, dry_run=True)
        assert pid is not None
        assert wt.status == TaskStatus.ACTIVE

    asyncio.run(_test())
