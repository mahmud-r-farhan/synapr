"""Validated filesystem paths for Git worktree tasks."""

from __future__ import annotations

import re
from pathlib import Path

_TASK_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,99}\Z", re.ASCII)


def resolve_worktree_path(root: Path, task_id: str) -> Path:
    """Return a task path contained by ``root``, rejecting traversal and symlinks."""
    if not isinstance(task_id, str) or not _TASK_ID_PATTERN.fullmatch(task_id):
        raise ValueError("Invalid task ID for worktree path.")

    resolved_root = root.resolve()
    path = resolved_root / task_id
    if path.is_symlink():
        raise ValueError("Worktree task path must not be a symlink.")
    resolved_path = path.resolve()
    if not resolved_path.is_relative_to(resolved_root):
        raise ValueError("Worktree task path escapes its configured root.")
    return resolved_path
