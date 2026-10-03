"""Domain models for Synapr multi-IDE swarm orchestration."""

import time
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    """Execution status for a task or worktree."""
    PENDING = "pending"
    PLANNING = "planning"
    DEBATING = "debating"
    PROVISIONED = "provisioned"
    DISPATCHED = "dispatched"
    ACTIVE = "active"
    RUNNING_TESTS = "running_tests"
    TESTS_PASSED = "tests_passed"
    TESTS_FAILED = "tests_failed"
    MERGING = "merging"
    CONFLICT_RESOLVING = "conflict_resolving"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class EditorType(str, Enum):
    """Supported IDE and editor types."""
    VSCODE = "vscode"
    VSCODE_INSIDERS = "vscode_insiders"
    CURSOR = "cursor"
    WINDSURF = "windsurf"
    ANTIGRAVITY = "antigravity"
    ANDROID_STUDIO = "android_studio"
    INTELLIJ = "intellij"
    PYCHARM = "pycharm"
    WEBSTORM = "webstorm"
    FLEET = "fleet"
    NEOVIM = "neovim"
    VIM = "vim"
    HELIX = "helix"
    CUSTOM = "custom"


class EditorInfo(BaseModel):
    """Information about an installed or configured code editor."""
    id: str
    name: str
    editor_type: EditorType
    executable_path: str
    version: str | None = None
    launch_args_template: list[str] = Field(default_factory=lambda: ["{path}"])
    is_available: bool = True
    description: str | None = None


class SubTask(BaseModel):
    """An isolated sub-task decomposed from the high-level goal."""
    id: str
    title: str
    description: str
    target_editor: str = "vscode"
    file_scope: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    instructions: str = ""
    test_command: str | None = None
    worktree_path: str | None = None
    branch_name: str | None = None
    status: TaskStatus = TaskStatus.PENDING
    assigned_agent: str | None = None
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
    metadata: dict[str, Any] = Field(default_factory=dict)


class DebateCritique(BaseModel):
    """A critique offered by a peer model during architectural debate."""
    critic_role: str
    model_name: str
    criticism: str
    risks_identified: list[str] = Field(default_factory=list)
    suggested_modifications: list[str] = Field(default_factory=list)
    verdict: str = "APPROVED"  # APPROVED | REVISE_REQUIRED | REJECTED


class DebateRound(BaseModel):
    """A round of multi-model debate on an orchestration plan."""
    round_number: int
    plan_proposal: str
    critiques: list[DebateCritique] = Field(default_factory=list)
    synthesis: str = ""
    consensus_score: float = 1.0  # 0.0 to 1.0
    approved: bool = True
    timestamp: float = Field(default_factory=time.time)


class ExecutionPlan(BaseModel):
    """The complete verified plan approved through multi-LLM debate."""
    id: str
    goal: str
    subtasks: list[SubTask] = Field(default_factory=list)
    debate_rounds: list[DebateRound] = Field(default_factory=list)
    final_consensus_score: float = 1.0
    base_branch: str = "master"
    created_at: float = Field(default_factory=time.time)
    metadata: dict[str, Any] = Field(default_factory=dict)


class WorktreeInstance(BaseModel):
    """Represents an active or provisioned Git worktree."""
    task_id: str
    branch: str
    path: str
    editor: str
    status: TaskStatus = TaskStatus.PROVISIONED
    created_at: float = Field(default_factory=time.time)
    is_locked: bool = False
    process_pid: int | None = None


class TestResult(BaseModel):
    """Output from running test suite in a worktree."""
    task_id: str
    command: str
    passed: bool
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    duration_seconds: float = 0.0


class MergeResult(BaseModel):
    """Outcome of attempting to merge a task worktree back to target branch."""
    task_id: str
    target_branch: str
    feature_branch: str
    success: bool
    had_conflicts: bool = False
    conflicted_files: list[str] = Field(default_factory=list)
    self_healed: bool = False
    message: str = ""
