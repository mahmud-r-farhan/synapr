"""Workspace, editor, perception, pipeline, and dashboard settings."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from .base import _Section


class WorktreeConfig(_Section):
    """Configuration for Git worktree directory isolation."""

    worktree_root: str = Field(default=".worktrees", description="Worktree parent directory")
    base_branch: str = Field(default="master", description="Fallback base branch")
    branch_prefix: str = Field(default="synapr/", description="Feature branch prefix")
    auto_cleanup_on_success: bool = Field(
        default=False, description="Delete the worktree after a successful merge"
    )
    isolate_git_index: bool = Field(default=True, description="Keep a dedicated git index")

class EditorConfig(_Section):
    """Configuration for IDE detection and dispatch."""

    preferred_editor: str | None = Field(default=None, description="Force a single editor id")
    editor_overrides: dict[str, str] = Field(
        default_factory=lambda: {
            "backend": "vscode",
            "frontend": "cursor",
            "android": "android_studio",
            "mobile": "android_studio",
        },
        description="Task keyword to editor id mapping",
    )
    custom_editor_paths: dict[str, str] = Field(
        default_factory=dict, description="Editor id to executable path overrides"
    )
    launch_detached: bool = Field(default=True, description="Spawn editors detached")

class PerceptionConfig(_Section):
    """Configuration for optical screen perception and terminal telemetry."""

    enabled: bool = Field(default=True, description="Enable the perception engine")
    poll_interval_seconds: float = Field(default=2.5, gt=0, description="Polling interval")
    ocr_engine: str = Field(
        default="auto", description="'auto', 'tesseract', 'windows_media' or 'regex_terminal'"
    )
    capture_screenshots: bool = Field(default=True, description="Persist window screenshots")
    screenshot_dir: str = Field(
        default=".synapr/screenshots", description="Screenshot output directory"
    )

class PipelineConfig(_Section):
    """Configuration for build, test, and self-healing merge pipeline."""

    auto_test: bool = Field(default=True, description="Run tests in every worktree")
    auto_merge: bool = Field(default=True, description="Merge passing branches automatically")
    max_self_healing_attempts: int = Field(
        default=3, ge=0, le=20, description="Resolver retry budget"
    )
    default_test_command: str | None = Field(default=None, description="Fallback test command")
    allow_force_merge: bool = Field(default=False, description="Merge even when tests fail")

class UIConfig(_Section):
    """Configuration for the local web dashboard and visual configurator."""

    host: str = Field(default="127.0.0.1", description="Dashboard bind address")
    port: int = Field(default=8765, ge=1, le=65535, description="Dashboard port")
    auto_open_browser: bool = Field(default=True, description="Open a browser on start")
    allow_config_writes: bool = Field(
        default=True, description="Allow the dashboard to edit and persist configuration"
    )
    allow_remote_origins: bool = Field(
        default=False, description="Relax CORS beyond localhost origins"
    )
    refresh_interval_seconds: float = Field(
        default=5.0, gt=0, description="Dashboard status polling interval"
    )
    theme: Literal["dark", "light"] = Field(default="dark", description="Dashboard theme")
