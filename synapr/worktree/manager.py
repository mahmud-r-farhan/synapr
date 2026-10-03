"""Programmatic Git Worktree provisioning and lifecycle management."""

import asyncio
import shutil
from pathlib import Path

from synapr.config import WorktreeConfig
from synapr.core.logger import logger
from synapr.core.models import TaskStatus, WorktreeInstance


class GitWorktreeError(Exception):
    """Raised when a Git worktree operation fails."""


class WorktreeManager:
    """Manages creation, tracking, locking, and pruning of isolated Git worktrees."""

    def __init__(
        self,
        repo_root: str | None = None,
        config: WorktreeConfig | None = None,
    ) -> None:
        self.repo_root = Path(repo_root or ".").resolve()
        self.config = config or WorktreeConfig()
        self.worktree_base = self.repo_root / self.config.worktree_root

    async def _run_git(self, args: list[str], cwd: Path | None = None) -> str:
        """Execute a git command asynchronously in the specified directory."""
        work_dir = cwd or self.repo_root
        cmd = ["git"] + args
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(work_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            if proc.returncode != 0:
                err_msg = stderr.decode("utf-8", errors="replace").strip()
                raise GitWorktreeError(f"Git command failed: {' '.join(cmd)}\nError: {err_msg}")
            return stdout.decode("utf-8", errors="replace").strip()
        except FileNotFoundError as exc:
            raise GitWorktreeError("Git executable not found in PATH.") from exc

    async def detect_base_branch(self) -> str:
        """Detect current active repository branch (e.g. master or main)."""
        try:
            branch = await self._run_git(["rev-parse", "--abbrev-ref", "HEAD"])
            return branch if branch and branch != "HEAD" else self.config.base_branch
        except Exception:
            return self.config.base_branch

    async def provision_worktree(
        self,
        task_id: str,
        editor: str = "vscode",
        base_branch: str | None = None,
        feature_branch: str | None = None,
    ) -> WorktreeInstance:
        """Create an isolated worktree and feature branch for a task."""
        self.worktree_base.mkdir(parents=True, exist_ok=True)
        worktree_path = self.worktree_base / task_id

        # Determine branch names
        base = base_branch or await self.detect_base_branch()
        branch = feature_branch or f"{self.config.branch_prefix}{task_id}"

        # Clean existing directory if stale
        if worktree_path.exists():
            logger.warning(f"Worktree path already exists at {worktree_path}. Attempting cleanup.")
            await self.cleanup_worktree(task_id, force=True, delete_branch=False)

        # Check if feature branch exists locally or remotely
        branch_exists = False
        try:
            await self._run_git(["rev-parse", "--verify", branch])
            branch_exists = True
        except GitWorktreeError:
            branch_exists = False

        # Add worktree
        if branch_exists:
            cmd = ["worktree", "add", str(worktree_path), branch]
        else:
            cmd = ["worktree", "add", "-b", branch, str(worktree_path), base]

        logger.info(f"Provisioning worktree: {worktree_path} on branch {branch} (base: {base})")
        await self._run_git(cmd)

        return WorktreeInstance(
            task_id=task_id,
            branch=branch,
            path=str(worktree_path.resolve()),
            editor=editor,
            status=TaskStatus.PROVISIONED,
        )

    async def list_worktrees(self) -> list[dict[str, str]]:
        """Query active worktrees via porcelain git interface."""
        output = await self._run_git(["worktree", "list", "--porcelain"])
        worktrees: list[dict[str, str]] = []
        current: dict[str, str] = {}

        for line in output.splitlines():
            line = line.strip()
            if not line:
                if current:
                    worktrees.append(current)
                    current = {}
                continue
            if line.startswith("worktree "):
                current["path"] = line.split(" ", 1)[1]
            elif line.startswith("HEAD "):
                current["head"] = line.split(" ", 1)[1]
            elif line.startswith("branch "):
                current["branch"] = line.split(" ", 1)[1]
            elif line == "locked":
                current["locked"] = "true"
            elif line == "prunable":
                current["prunable"] = "true"

        if current:
            worktrees.append(current)
        return worktrees

    async def lock_worktree(self, task_id: str, reason: str = "Synapr active worker") -> None:
        """Lock worktree to prevent accidental pruning."""
        worktree_path = self.worktree_base / task_id
        if worktree_path.exists():
            await self._run_git(["worktree", "lock", str(worktree_path), "--reason", reason])

    async def unlock_worktree(self, task_id: str) -> None:
        """Unlock a previously locked worktree."""
        worktree_path = self.worktree_base / task_id
        if worktree_path.exists():
            await self._run_git(["worktree", "unlock", str(worktree_path)])

    async def check_uncommitted_changes(self, task_id: str) -> bool:
        """Return True if worktree has uncommitted modifications or untracked files."""
        worktree_path = self.worktree_base / task_id
        if not worktree_path.exists():
            return False
        status = await self._run_git(["status", "--porcelain"], cwd=worktree_path)
        return len(status.strip()) > 0

    async def cleanup_worktree(
        self,
        task_id: str,
        force: bool = True,
        delete_branch: bool = False,
    ) -> None:
        """Remove worktree safely and prune references."""
        worktree_path = self.worktree_base / task_id
        branch = f"{self.config.branch_prefix}{task_id}"

        if worktree_path.exists():
            try:
                # Unlock first if locked
                await self.unlock_worktree(task_id)
            except Exception:
                pass

            args = ["worktree", "remove"]
            if force:
                args.append("--force")
            args.append(str(worktree_path))

            try:
                await self._run_git(args)
            except Exception as e:
                logger.warning(f"Git worktree remove failed: {e}. Falling back to filesystem deletion.")
                if worktree_path.is_dir():
                    shutil.rmtree(worktree_path, ignore_errors=True)

        # Prune git internal worktree references
        await self._run_git(["worktree", "prune"])

        # Optionally delete branch
        if delete_branch:
            try:
                await self._run_git(["branch", "-D" if force else "-d", branch])
            except Exception:
                pass

    async def prune_all(self) -> None:
        """Clean all stale worktrees."""
        await self._run_git(["worktree", "prune"])
