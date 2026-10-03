"""Task ID validation for worktree lifecycle operations."""

from __future__ import annotations

import re

_TASK_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,99}\Z", re.ASCII)


def is_valid_task_id(task_id: str) -> bool:
    """Return whether an ID is a single safe worktree directory component."""
    return isinstance(task_id, str) and _TASK_ID_PATTERN.fullmatch(task_id) is not None
