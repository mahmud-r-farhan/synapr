"""Runtime environment variable declarations."""

from .env_types import EnvVarSpec

SPECS: tuple[EnvVarSpec, ...] = (
    EnvVarSpec(
        name="SYNAPR_WORKTREE_ROOT",
        path="worktree.worktree_root",
        description="Directory (relative to the repo) holding isolated worktrees.",
        example=".worktrees",
    ),
    EnvVarSpec(
        name="SYNAPR_BASE_BRANCH",
        path="worktree.base_branch",
        description="Fallback base branch when detection fails.",
        example="main",
    ),
    EnvVarSpec(
        name="SYNAPR_BRANCH_PREFIX",
        path="worktree.branch_prefix",
        description="Prefix applied to every generated feature branch.",
        example="synapr/",
    ),
    EnvVarSpec(
        name="SYNAPR_AUTO_CLEANUP",
        path="worktree.auto_cleanup_on_success",
        kind="bool",
        description="Remove a worktree automatically once its merge succeeds.",
        example="false",
    ),
    EnvVarSpec(
        name="SYNAPR_PREFERRED_EDITOR",
        path="editor.preferred_editor",
        description="Force a single editor id (e.g. vscode, cursor, android_studio).",
        example="vscode",
    ),
    EnvVarSpec(
        name="SYNAPR_EDITOR_OVERRIDES",
        path="editor.editor_overrides",
        kind="json",
        description="JSON map of task keyword -> editor id.",
        example='{"backend":"vscode","mobile":"android_studio"}',
    ),
    EnvVarSpec(
        name="SYNAPR_CUSTOM_EDITOR_PATHS",
        path="editor.custom_editor_paths",
        kind="json",
        description="JSON map of editor id -> absolute executable path.",
        example='{"myeditor":"/usr/local/bin/myeditor"}',
    ),
    EnvVarSpec(
        name="SYNAPR_LAUNCH_DETACHED",
        path="editor.launch_detached",
        kind="bool",
        description="Spawn editors detached from the Synapr process.",
        example="true",
    ),
    EnvVarSpec(
        name="SYNAPR_PERCEPTION_ENABLED",
        path="perception.enabled",
        kind="bool",
        description="Enable optical window perception and terminal telemetry.",
        example="true",
    ),
    EnvVarSpec(
        name="SYNAPR_PERCEPTION_INTERVAL",
        path="perception.poll_interval_seconds",
        kind="float",
        description="Seconds between perception polls.",
        example="2.5",
    ),
    EnvVarSpec(
        name="SYNAPR_OCR_ENGINE",
        path="perception.ocr_engine",
        description="OCR backend: auto, tesseract, windows_media or regex_terminal.",
        example="auto",
    ),
    EnvVarSpec(
        name="SYNAPR_CAPTURE_SCREENSHOTS",
        path="perception.capture_screenshots",
        kind="bool",
        description="Persist window screenshots for later inspection.",
        example="true",
    ),
    EnvVarSpec(
        name="SYNAPR_SCREENSHOT_DIR",
        path="perception.screenshot_dir",
        description="Directory where screenshots are written.",
        example=".synapr/screenshots",
    ),
    EnvVarSpec(
        name="SYNAPR_AUTO_TEST",
        path="pipeline.auto_test",
        kind="bool",
        description="Run the detected test suite in every worktree.",
        example="true",
    ),
    EnvVarSpec(
        name="SYNAPR_AUTO_MERGE",
        path="pipeline.auto_merge",
        kind="bool",
        description="Merge passing branches back into the base branch.",
        example="true",
    ),
    EnvVarSpec(
        name="SYNAPR_MAX_HEALING_ATTEMPTS",
        path="pipeline.max_self_healing_attempts",
        kind="int",
        description="How many times the resolver may retry a conflicted merge.",
        example="3",
    ),
    EnvVarSpec(
        name="SYNAPR_TEST_COMMAND",
        path="pipeline.default_test_command",
        description="Fallback test command when auto-detection finds nothing.",
        example="pytest -q",
    ),
    EnvVarSpec(
        name="SYNAPR_ALLOW_FORCE_MERGE",
        path="pipeline.allow_force_merge",
        kind="bool",
        description="Permit merging even when the test suite fails.",
        example="false",
    )
)
