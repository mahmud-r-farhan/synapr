"""Unit tests for build & test runner and self-healing merge engine."""

import asyncio
from pathlib import Path

from synapr.core.models import SubTask, WorktreeInstance
from synapr.merger.pipeline import TestPipeline
from synapr.merger.self_healing import SelfHealingResolver


def test_auto_detect_test_command(tmp_path: Path) -> None:
    """Test auto-detection of test commands based on directory contents."""
    pipeline = TestPipeline()

    (tmp_path / "Cargo.toml").write_text("[package]\nname = 'test'\n", encoding="utf-8")
    assert pipeline.auto_detect_command(str(tmp_path)) == "cargo test"

    (tmp_path / "Cargo.toml").unlink()
    (tmp_path / "package.json").write_text("{}", encoding="utf-8")
    assert pipeline.auto_detect_command(str(tmp_path)) == "npm test"


def test_run_tests(tmp_path: Path) -> None:
    """Test test runner execution with passing command."""
    async def _test() -> None:
        pipeline = TestPipeline()
        task = SubTask(
            id="task-test-suite",
            title="Testing",
            description="Testing",
            test_command="python -c \"print('All tests passed')\"",
        )
        wt = WorktreeInstance(
            task_id=task.id,
            branch="synapr/test",
            path=str(tmp_path),
            editor="system",
        )

        res = await pipeline.run_tests(wt, task)
        assert res.passed is True
        assert "All tests passed" in res.stdout

    asyncio.run(_test())


def test_self_healing_conflict_resolution() -> None:
    """Test resolver method cleans conflict markers."""
    async def _test() -> None:
        resolver = SelfHealingResolver()
        conflict_text = (
            "<<<<<<< HEAD\n"
            "def status(): return 'healthy'\n"
            "=======\n"
            "def status(): return 'ok'\n"
            ">>>>>>> feature/task\n"
        )

        resolved = await resolver._resolve_file_conflict(
            file_name="status.py",
            conflict_text=conflict_text,
            task_info="Merge status function",
        )
        assert resolved is not None
        assert "<<<<<<<" not in resolved
        assert ">>>>>>>" not in resolved

    asyncio.run(_test())
