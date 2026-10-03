"""Automated build and test suite execution within isolated worktrees."""

import asyncio
import time
from pathlib import Path

from synapr.core.events import bus
from synapr.core.logger import logger
from synapr.core.models import SubTask, TaskStatus, TestResult, WorktreeInstance


class TestPipeline:
    """Executes local build and test suites within specific worktree directories."""

    __test__ = False

    def __init__(self, default_command: str | None = None) -> None:
        self.default_command = default_command

    def auto_detect_command(self, worktree_path: str) -> str:
        """Detect the appropriate test runner based on files present in the worktree."""
        p = Path(worktree_path)
        if (p / "Cargo.toml").exists():
            return "cargo test"
        if (p / "package.json").exists():
            return "npm test"
        if (p / "pyproject.toml").exists() or (p / "tests").exists():
            return "pytest -q"
        if (p / "go.mod").exists():
            return "go test ./..."
        if (p / "gradlew").exists() or (p / "build.gradle").exists():
            return "./gradlew test"
        return self.default_command or "python -m unittest discover -s tests -p 'test_*.py'"

    async def run_tests(
        self,
        worktree: WorktreeInstance,
        task: SubTask,
        custom_command: str | None = None,
    ) -> TestResult:
        """Execute the test command inside the worktree directory asynchronously."""
        cmd_str = custom_command or task.test_command or self.auto_detect_command(worktree.path)
        logger.info(f"Running test suite for {task.id} in {worktree.path}: {cmd_str}")

        worktree.status = TaskStatus.RUNNING_TESTS
        bus.emit("tests:start", {"task_id": task.id, "command": cmd_str, "worktree": worktree.path})

        start_time = time.time()
        try:
            # Run via shell to support command strings with flags
            proc = await asyncio.create_subprocess_shell(
                cmd_str,
                cwd=worktree.path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout_b, stderr_b = await proc.communicate()
            duration = time.time() - start_time
            passed = proc.returncode == 0

            stdout_str = stdout_b.decode("utf-8", errors="replace").strip()
            stderr_str = stderr_b.decode("utf-8", errors="replace").strip()

            result = TestResult(
                task_id=task.id,
                command=cmd_str,
                passed=passed,
                stdout=stdout_str,
                stderr=stderr_str,
                exit_code=proc.returncode or 0,
                duration_seconds=round(duration, 3),
            )

            worktree.status = TaskStatus.TESTS_PASSED if passed else TaskStatus.TESTS_FAILED
            bus.emit(
                "tests:complete",
                {
                    "task_id": task.id,
                    "passed": passed,
                    "duration": duration,
                    "exit_code": proc.returncode,
                },
            )

            logger.info(
                f"Test suite finished for {task.id}: {'PASSED' if passed else 'FAILED'} "
                f"(exit code: {proc.returncode}, {duration:.2f}s)"
            )
            return result
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"Test suite execution error in {worktree.path}: {e}")
            worktree.status = TaskStatus.TESTS_FAILED
            return TestResult(
                task_id=task.id,
                command=cmd_str,
                passed=False,
                stdout="",
                stderr=str(e),
                exit_code=1,
                duration_seconds=round(duration, 3),
            )
