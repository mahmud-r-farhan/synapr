"""Configuration management for Synapr with Pydantic V2.

This module is the single source of truth for every tunable knob in Synapr.

Three layers are supported, applied in increasing order of precedence:

1. **Built-in defaults** declared on the models below.
2. **A JSON configuration file** (``synapr.config.json``, ``.synapr/config.json``
   or ``~/.synapr/config.json``).
3. **Environment variables** (optionally sourced from a ``.env`` file), declared
   in :data:`ENV_VAR_SPECS`.

Every single setting can therefore be declared as an environment variable *or*
edited visually at runtime through the web dashboard (``synapr ui`` →
*Configuration*), which persists changes back to the JSON file through
:mod:`synapr.core.config_service`.
"""

from __future__ import annotations

import json
import os
import stat
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, get_args, get_origin

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, field_validator

__all__ = [
    "ENV_PREFIX",
    "ENV_VAR_SPECS",
    "SECRET_MASK",
    "SUPPORTED_PROVIDERS",
    "EditorConfig",
    "EnvVarSpec",
    "GatewayConfig",
    "PerceptionConfig",
    "PipelineConfig",
    "SynaprConfig",
    "UIConfig",
    "WorktreeConfig",
    "default_config_path",
    "discover_config_file",
    "env_var_report",
    "get_by_path",
    "load_env_file",
    "redact_secret",
    "render_env_example",
    "set_by_path",
    "write_env_file",
]

ENV_PREFIX = "SYNAPR_"
"""Canonical prefix for every Synapr environment variable."""

SECRET_MASK = "••••••••"
"""Placeholder returned instead of secret values. Sending it back is a no-op."""

SUPPORTED_PROVIDERS: tuple[str, ...] = (
    "mock",
    "ollama",
    "openai",
    "openrouter",
    "groq",
    "lmstudio",
    "vllm",
)
"""Providers the gateway knows how to talk to (anything else degrades to mock)."""

CONFIG_FILENAMES: tuple[str, ...] = ("synapr.config.json", ".synapr/config.json")

_TRUTHY = {"1", "true", "t", "yes", "y", "on"}
_FALSY = {"0", "false", "f", "no", "n", "off"}


# --------------------------------------------------------------------------------------
# Environment variable registry
# --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class EnvVarSpec:
    """Declarative binding between an environment variable and a config field."""

    name: str
    path: str
    kind: Literal["str", "int", "float", "bool", "csv", "json"] = "str"
    secret: bool = False
    aliases: tuple[str, ...] = ()
    description: str = ""
    example: str = ""

    @property
    def names(self) -> tuple[str, ...]:
        """All accepted variable names, canonical first."""
        return (self.name, *self.aliases)

    def read(self, environ: dict[str, str] | None = None) -> tuple[str, str] | None:
        """Return ``(variable_name, raw_value)`` for the first variable that is set."""
        env = environ if environ is not None else os.environ  # type: ignore[assignment]
        for name in self.names:
            raw = env.get(name)
            if raw is not None and raw != "":
                return name, raw
        return None


ENV_VAR_SPECS: tuple[EnvVarSpec, ...] = (
    # -- project -----------------------------------------------------------------
    EnvVarSpec(
        name="SYNAPR_PROJECT_NAME",
        path="project_name",
        description="Human readable project label shown in the dashboard.",
        example="Synapr Swarm",
    ),
    # -- gateway -----------------------------------------------------------------
    EnvVarSpec(
        name="SYNAPR_PROVIDER",
        path="gateway.default_provider",
        aliases=("SYNAPR_GATEWAY_PROVIDER",),
        description=f"Active LLM provider. One of: {', '.join(SUPPORTED_PROVIDERS)}.",
        example="ollama",
    ),
    EnvVarSpec(
        name="SYNAPR_OLLAMA_BASE_URL",
        path="gateway.ollama_base_url",
        aliases=("OLLAMA_BASE_URL",),
        description="Base URL of the local Ollama daemon.",
        example="http://localhost:11434",
    ),
    EnvVarSpec(
        name="SYNAPR_OPENAI_BASE_URL",
        path="gateway.openai_base_url",
        aliases=("OPENAI_BASE_URL",),
        description="OpenAI-compatible endpoint used for the 'openai' provider.",
        example="https://api.openai.com/v1",
    ),
    EnvVarSpec(
        name="SYNAPR_OPENROUTER_BASE_URL",
        path="gateway.openrouter_base_url",
        description="OpenRouter API base URL.",
        example="https://openrouter.ai/api/v1",
    ),
    EnvVarSpec(
        name="SYNAPR_GROQ_BASE_URL",
        path="gateway.groq_base_url",
        description="Groq API base URL.",
        example="https://api.groq.com/openai/v1",
    ),
    EnvVarSpec(
        name="SYNAPR_LMSTUDIO_BASE_URL",
        path="gateway.lmstudio_base_url",
        description="LM Studio local server base URL.",
        example="http://localhost:1234/v1",
    ),
    EnvVarSpec(
        name="SYNAPR_VLLM_BASE_URL",
        path="gateway.vllm_base_url",
        description="vLLM OpenAI-compatible server base URL.",
        example="http://localhost:8000/v1",
    ),
    EnvVarSpec(
        name="SYNAPR_OPENAI_API_KEY",
        path="gateway.openai_api_key",
        secret=True,
        aliases=("OPENAI_API_KEY",),
        description="API key for OpenAI (never written to the config file).",
        example="sk-...",
    ),
    EnvVarSpec(
        name="SYNAPR_OPENROUTER_API_KEY",
        path="gateway.openrouter_api_key",
        secret=True,
        aliases=("OPENROUTER_API_KEY",),
        description="API key for OpenRouter.",
        example="sk-or-...",
    ),
    EnvVarSpec(
        name="SYNAPR_GROQ_API_KEY",
        path="gateway.groq_api_key",
        secret=True,
        aliases=("GROQ_API_KEY",),
        description="API key for Groq.",
        example="gsk_...",
    ),
    EnvVarSpec(
        name="SYNAPR_PLANNER_MODEL",
        path="gateway.planner_model",
        description="Model used to decompose goals into subtasks.",
        example="qwen2.5-coder:7b",
    ),
    EnvVarSpec(
        name="SYNAPR_CRITIC_MODELS",
        path="gateway.critic_models",
        kind="csv",
        description="Comma separated adversarial reviewer models.",
        example="llama3.2:latest,mistral:latest",
    ),
    EnvVarSpec(
        name="SYNAPR_ARBITER_MODEL",
        path="gateway.arbiter_model",
        description="Model that synthesises the consensus verdict.",
        example="qwen2.5-coder:7b",
    ),
    EnvVarSpec(
        name="SYNAPR_RESOLVER_MODEL",
        path="gateway.resolver_model",
        description="Model used for self-healing merge conflict resolution.",
        example="qwen2.5-coder:7b",
    ),
    EnvVarSpec(
        name="SYNAPR_VISION_MODEL",
        path="gateway.vision_model",
        description="Multi-modal model used by the optical perception engine.",
        example="llava:latest",
    ),
    EnvVarSpec(
        name="SYNAPR_TIMEOUT_SECONDS",
        path="gateway.timeout_seconds",
        kind="float",
        description="Per-request LLM timeout in seconds.",
        example="60",
    ),
    EnvVarSpec(
        name="SYNAPR_TEMPERATURE",
        path="gateway.temperature",
        kind="float",
        description="Sampling temperature for all roles (0.0 - 2.0).",
        example="0.2",
    ),
    EnvVarSpec(
        name="SYNAPR_MAX_TOKENS",
        path="gateway.max_tokens",
        kind="int",
        description="Maximum tokens generated per completion.",
        example="4096",
    ),
    # -- worktree ----------------------------------------------------------------
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
    # -- editor ------------------------------------------------------------------
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
    # -- perception --------------------------------------------------------------
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
    # -- pipeline ----------------------------------------------------------------
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
    ),
    # -- ui ----------------------------------------------------------------------
    EnvVarSpec(
        name="SYNAPR_UI_HOST",
        path="ui.host",
        description="Bind address of the local dashboard.",
        example="127.0.0.1",
    ),
    EnvVarSpec(
        name="SYNAPR_UI_PORT",
        path="ui.port",
        kind="int",
        description="TCP port of the local dashboard.",
        example="8765",
    ),
    EnvVarSpec(
        name="SYNAPR_UI_OPEN_BROWSER",
        path="ui.auto_open_browser",
        kind="bool",
        description="Open the default browser when the dashboard starts.",
        example="true",
    ),
    EnvVarSpec(
        name="SYNAPR_UI_ALLOW_CONFIG_WRITES",
        path="ui.allow_config_writes",
        kind="bool",
        description="Allow the dashboard to edit and persist the configuration.",
        example="true",
    ),
    EnvVarSpec(
        name="SYNAPR_UI_ALLOW_REMOTE_ORIGINS",
        path="ui.allow_remote_origins",
        kind="bool",
        description="Relax CORS so non-localhost origins may call the API.",
        example="false",
    ),
    EnvVarSpec(
        name="SYNAPR_UI_REFRESH_SECONDS",
        path="ui.refresh_interval_seconds",
        kind="float",
        description="Dashboard polling interval for status widgets.",
        example="5",
    ),
)

ENV_SPECS_BY_PATH: dict[str, EnvVarSpec] = {spec.path: spec for spec in ENV_VAR_SPECS}


# --------------------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------------------


def redact_secret(value: str | None) -> str | None:
    """Return a masked representation of a secret, keeping the last 4 characters."""
    if not value:
        return None
    if len(value) <= 4:
        return SECRET_MASK
    return f"{SECRET_MASK}{value[-4:]}"


def coerce_env_value(kind: str, raw: str) -> Any:
    """Convert a raw environment string into the type expected by the config field."""
    text = raw.strip()
    if kind == "bool":
        lowered = text.lower()
        if lowered in _TRUTHY:
            return True
        if lowered in _FALSY:
            return False
        raise ValueError(f"Expected a boolean value, received {raw!r}")
    if kind == "int":
        return int(text)
    if kind == "float":
        return float(text)
    if kind == "csv":
        return [item.strip() for item in text.split(",") if item.strip()]
    if kind == "json":
        parsed = json.loads(text)
        if not isinstance(parsed, dict):
            raise ValueError("Expected a JSON object")
        return parsed
    return text


def get_by_path(model: BaseModel, path: str) -> Any:
    """Read a nested attribute using a dotted path (``gateway.planner_model``)."""
    current: Any = model
    for part in path.split("."):
        if not isinstance(current, BaseModel) or part not in type(current).model_fields:
            raise KeyError(f"Unknown configuration path: {path}")
        current = getattr(current, part)
    return current


def set_by_path(model: BaseModel, path: str, value: Any) -> None:
    """Assign a nested attribute using a dotted path, validating the new value."""
    parts = path.split(".")
    current: Any = model
    for part in parts[:-1]:
        if not isinstance(current, BaseModel) or part not in type(current).model_fields:
            raise KeyError(f"Unknown configuration path: {path}")
        current = getattr(current, part)
    leaf = parts[-1]
    if not isinstance(current, BaseModel) or leaf not in type(current).model_fields:
        raise KeyError(f"Unknown configuration path: {path}")
    setattr(current, leaf, value)


def deep_merge(base: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge ``updates`` into a copy of ``base``."""
    merged = dict(base)
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def parse_env_text(text: str) -> dict[str, str]:
    """Parse ``.env`` style content into a mapping (supports ``export`` and quotes)."""
    values: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.lower().startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if not key:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        values[key] = value
    return values


def load_env_file(path: str | Path = ".env", override: bool = False) -> dict[str, str]:
    """Load a ``.env`` file into :data:`os.environ` and return the parsed mapping."""
    env_path = Path(path)
    if not env_path.is_file():
        return {}
    try:
        values = parse_env_text(env_path.read_text(encoding="utf-8"))
    except OSError:
        return {}
    for key, value in values.items():
        if override or key not in os.environ:
            os.environ[key] = value
    return values


def write_env_file(
    values: dict[str, str],
    path: str | Path = ".env",
    remove: list[str] | None = None,
) -> Path:
    """Create or update a ``.env`` file, preserving unrelated lines and comments."""
    env_path = Path(path)
    removals = set(remove or [])
    lines: list[str] = []
    if env_path.is_file():
        lines = env_path.read_text(encoding="utf-8").splitlines()

    remaining = dict(values)
    output: list[str] = []
    for line in lines:
        stripped = line.strip()
        candidate = stripped[7:].strip() if stripped.lower().startswith("export ") else stripped
        key = candidate.partition("=")[0].strip() if "=" in candidate else ""
        if key and key in removals:
            continue
        if key and key in remaining:
            output.append(f"{key}={remaining.pop(key)}")
        else:
            output.append(line)

    if remaining:
        if output and output[-1].strip():
            output.append("")
        output.append("# Managed by Synapr")
        output.extend(f"{key}={value}" for key, value in remaining.items())

    env_path.parent.mkdir(parents=True, exist_ok=True)
    env_path.write_text("\n".join(output).rstrip("\n") + "\n", encoding="utf-8")
    _harden_permissions(env_path)
    return env_path


def _harden_permissions(path: Path) -> None:
    """Best-effort ``chmod 600`` so secrets are not world readable on POSIX hosts."""
    if os.name == "nt":
        return
    try:
        path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass


def default_config_path(base_dir: str | Path | None = None) -> Path:
    """Return the canonical configuration file location for a project directory."""
    return Path(base_dir or ".").resolve() / CONFIG_FILENAMES[0]


def discover_config_file(
    config_path: str | Path | None = None,
    base_dir: str | Path | None = None,
) -> Path | None:
    """Locate the configuration file Synapr would load, or ``None`` when absent."""
    root = Path(base_dir or ".")
    candidates: list[Path] = []
    if config_path:
        candidates.append(Path(config_path))
    candidates.extend(root / name for name in CONFIG_FILENAMES)
    candidates.append(Path.home() / ".synapr" / "config.json")
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


# --------------------------------------------------------------------------------------
# Models
# --------------------------------------------------------------------------------------


class _Section(BaseModel):
    """Base class enabling assignment validation for every configuration section."""

    model_config = ConfigDict(validate_assignment=True, extra="ignore")


class GatewayConfig(_Section):
    """Configuration for local LLM engines and remote gateways."""

    default_provider: str = Field(
        default="mock",
        description="Active provider: 'mock', 'ollama', 'openai', 'groq', 'openrouter', 'lmstudio', 'vllm'",
    )
    ollama_base_url: str = Field(
        default="http://localhost:11434", description="Local Ollama daemon URL"
    )
    openai_base_url: str = Field(
        default="https://api.openai.com/v1", description="OpenAI-compatible endpoint"
    )
    openrouter_base_url: str = Field(
        default="https://openrouter.ai/api/v1", description="OpenRouter endpoint"
    )
    groq_base_url: str = Field(
        default="https://api.groq.com/openai/v1", description="Groq endpoint"
    )
    lmstudio_base_url: str = Field(
        default="http://localhost:1234/v1", description="LM Studio local server endpoint"
    )
    vllm_base_url: str = Field(
        default="http://localhost:8000/v1", description="vLLM local server endpoint"
    )
    openai_api_key: str | None = Field(default=None, description="OpenAI API key")
    openrouter_api_key: str | None = Field(default=None, description="OpenRouter API key")
    groq_api_key: str | None = Field(default=None, description="Groq API key")

    # Models assigned to specific roles
    planner_model: str = Field(
        default="qwen2.5-coder:7b", description="Model that decomposes goals into subtasks"
    )
    critic_models: list[str] = Field(
        default_factory=lambda: ["llama3.2:latest", "mistral:latest"],
        description="Adversarial reviewer models used during the consensus debate",
    )
    arbiter_model: str = Field(
        default="qwen2.5-coder:7b", description="Model synthesising the final verdict"
    )
    resolver_model: str = Field(
        default="qwen2.5-coder:7b", description="Model resolving merge conflicts"
    )
    vision_model: str = Field(
        default="llava:latest", description="Multi-modal model for screen perception"
    )

    timeout_seconds: float = Field(default=60.0, gt=0, description="Per-request timeout")
    temperature: float = Field(default=0.2, ge=0.0, le=2.0, description="Sampling temperature")
    max_tokens: int = Field(default=4096, gt=0, description="Maximum generated tokens")

    @field_validator("default_provider", mode="before")
    @classmethod
    def _normalise_provider(cls, value: Any) -> Any:
        """Lower-case the provider; unknown values are kept (gateway degrades to mock)."""
        if isinstance(value, str):
            return value.strip().lower()
        return value

    @field_validator(
        "openai_api_key", "openrouter_api_key", "groq_api_key", mode="before"
    )
    @classmethod
    def _empty_secret_is_none(cls, value: Any) -> Any:
        """Treat empty strings as 'unset' so the UI can clear a key."""
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @property
    def is_local_provider(self) -> bool:
        """True when inference never leaves the host machine."""
        return self.default_provider in {"mock", "ollama", "lmstudio", "vllm"}

    def base_url_for(self, provider: str) -> str:
        """Return the configured base URL for an OpenAI-compatible provider."""
        return {
            "openai": self.openai_base_url,
            "openrouter": self.openrouter_base_url,
            "groq": self.groq_base_url,
            "lmstudio": self.lmstudio_base_url,
            "vllm": self.vllm_base_url,
        }.get(provider, self.openai_base_url)

    def api_key_for(self, provider: str) -> str:
        """Return the API key for a provider, falling back to the environment."""
        mapping: dict[str, str] = {
            "openai": self.openai_api_key or os.getenv("OPENAI_API_KEY") or "",
            "openrouter": self.openrouter_api_key or os.getenv("OPENROUTER_API_KEY") or "",
            "groq": self.groq_api_key or os.getenv("GROQ_API_KEY") or "",
            "lmstudio": "not-needed",
            "vllm": "not-needed",
        }
        return mapping.get(provider, "")


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


@dataclass
class ConfigMeta:
    """Provenance information attached to a loaded :class:`SynaprConfig`."""

    source_path: str | None = None
    env_file: str | None = None
    env_overrides: dict[str, str] = field(default_factory=dict)
    pre_env_values: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


class SynaprConfig(_Section):
    """Root configuration for Synapr local orchestrator."""

    project_name: str = Field(default="Synapr Project", description="Project label")
    gateway: GatewayConfig = Field(default_factory=GatewayConfig)
    worktree: WorktreeConfig = Field(default_factory=WorktreeConfig)
    editor: EditorConfig = Field(default_factory=EditorConfig)
    perception: PerceptionConfig = Field(default_factory=PerceptionConfig)
    pipeline: PipelineConfig = Field(default_factory=PipelineConfig)
    ui: UIConfig = Field(default_factory=UIConfig)

    _meta: ConfigMeta = PrivateAttr(default_factory=ConfigMeta)

    # ------------------------------------------------------------------ provenance
    @property
    def meta(self) -> ConfigMeta:
        """Where this configuration came from (file path, env overrides, errors)."""
        return self._meta

    @meta.setter
    def meta(self, value: ConfigMeta) -> None:
        self._meta = value

    # ------------------------------------------------------------------ loading
    @classmethod
    def load(
        cls,
        config_path: str | None = None,
        *,
        use_env: bool = True,
        env_file: str | Path | None = ".env",
        base_dir: str | Path | None = None,
    ) -> SynaprConfig:
        """Load configuration from a file (if any) and layer environment overrides on top.

        Precedence: defaults < JSON file < ``.env`` file < real environment variables.
        """
        meta = ConfigMeta()
        cfg = cls()

        found = discover_config_file(config_path, base_dir)
        if found is not None:
            try:
                data = json.loads(found.read_text(encoding="utf-8"))
                if not isinstance(data, dict):
                    raise ValueError("Configuration root must be a JSON object")
                cfg = cls.model_validate(data)
                meta.source_path = str(found.resolve())
            except Exception as exc:  # pragma: no cover - defensive, exercised in tests
                meta.errors.append(f"Failed to load {found}: {exc}")

        if use_env:
            if env_file:
                loaded = load_env_file(Path(base_dir or ".") / env_file)
                if loaded:
                    meta.env_file = str((Path(base_dir or ".") / env_file).resolve())
            cfg.apply_env(meta=meta)

        cfg.meta = meta
        return cfg

    def apply_env(
        self,
        environ: dict[str, str] | None = None,
        *,
        meta: ConfigMeta | None = None,
    ) -> SynaprConfig:
        """Apply every environment variable declared in :data:`ENV_VAR_SPECS`."""
        target_meta = meta if meta is not None else self.meta
        env = environ if environ is not None else dict(os.environ)
        provider_explicit = False

        # Revert values whose environment variable disappeared since the last pass,
        # so unsetting a variable in the dashboard restores the file/default value.
        for path, _var in list(target_meta.env_overrides.items()):
            spec = ENV_SPECS_BY_PATH.get(path)
            if spec is not None and spec.read(env) is not None:
                continue
            if path in target_meta.pre_env_values:
                try:
                    set_by_path(self, path, target_meta.pre_env_values.pop(path))
                except Exception as exc:  # pragma: no cover - defensive
                    target_meta.errors.append(f"{path}: {exc}")
            target_meta.env_overrides.pop(path, None)

        for spec in ENV_VAR_SPECS:
            hit = spec.read(env)
            if hit is None:
                continue
            name, raw = hit
            try:
                value = coerce_env_value(spec.kind, raw)
            except Exception as exc:
                target_meta.errors.append(f"{name}: {exc}")
                continue
            try:
                previous = get_by_path(self, spec.path)
                set_by_path(self, spec.path, value)
            except Exception as exc:
                target_meta.errors.append(f"{name}: {exc}")
                continue
            target_meta.env_overrides[spec.path] = name
            target_meta.pre_env_values.setdefault(spec.path, previous)
            if spec.path == "gateway.default_provider":
                provider_explicit = True

        # Legacy convenience: an OpenAI key alone promotes the provider away from mock.
        if (
            not provider_explicit
            and self.gateway.default_provider == "mock"
            and (env.get("OPENAI_API_KEY") or env.get("SYNAPR_OPENAI_API_KEY"))
        ):
            target_meta.pre_env_values.setdefault(
                "gateway.default_provider", self.gateway.default_provider
            )
            self.gateway.default_provider = "openai"
            target_meta.env_overrides["gateway.default_provider"] = (
                "OPENAI_API_KEY" if env.get("OPENAI_API_KEY") else "SYNAPR_OPENAI_API_KEY"
            )

        if meta is None:
            self.meta = target_meta
        return self

    # ------------------------------------------------------------------ mutation
    def apply_updates(self, updates: dict[str, Any]) -> SynaprConfig:
        """Return a new validated configuration with ``updates`` deep-merged in.

        Masked secret placeholders coming back from the UI are ignored so that
        displaying a redacted key never destroys the real one.
        """
        cleaned = _strip_masked_secrets(updates)
        merged = deep_merge(self.model_dump(mode="json"), cleaned)
        new_cfg = type(self).model_validate(merged)
        new_cfg.meta = ConfigMeta(
            source_path=self.meta.source_path,
            env_file=self.meta.env_file,
            env_overrides=dict(self.meta.env_overrides),
            pre_env_values=dict(self.meta.pre_env_values),
        )
        return new_cfg

    # ------------------------------------------------------------------ export
    def to_dict(self, *, redact: bool = False) -> dict[str, Any]:
        """Serialise the configuration, optionally masking secret values."""
        data = self.model_dump(mode="json")
        if redact:
            for spec in ENV_VAR_SPECS:
                if not spec.secret:
                    continue
                try:
                    value = get_by_path(self, spec.path)
                except KeyError:  # pragma: no cover - defensive
                    continue
                _assign_dict_path(data, spec.path, redact_secret(value))
        return data

    def secret_status(self) -> dict[str, bool]:
        """Map each secret config path to whether a value is currently configured."""
        status: dict[str, bool] = {}
        for spec in ENV_VAR_SPECS:
            if spec.secret:
                try:
                    status[spec.path] = bool(get_by_path(self, spec.path))
                except KeyError:  # pragma: no cover - defensive
                    status[spec.path] = False
        return status

    def file_state(self) -> dict[str, Any]:
        """Serialisable state excluding values that were injected by the environment."""
        data = self.model_dump(mode="json")
        for path, previous in self.meta.pre_env_values.items():
            _assign_dict_path(data, path, previous)
        return data

    def save(
        self,
        output_path: str | Path = "synapr.config.json",
        *,
        include_env_sourced: bool = False,
    ) -> Path:
        """Persist configuration to a JSON file atomically.

        Values provided by environment variables are *not* baked into the file by
        default, keeping the environment authoritative (and keys out of git).
        """
        target = Path(output_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = self.model_dump(mode="json") if include_env_sourced else self.file_state()
        serialised = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"

        fd, tmp_name = tempfile.mkstemp(
            prefix=".synapr-config-", suffix=".tmp", dir=str(target.parent or ".")
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(serialised)
            os.replace(tmp_name, target)
        except BaseException:
            Path(tmp_name).unlink(missing_ok=True)
            raise

        # mkstemp() creates 0600 files; relax to a normal config mode unless the
        # payload actually contains a secret, in which case keep it owner-only.
        if _payload_has_secret(payload):
            _harden_permissions(target)
        elif os.name != "nt":
            try:
                target.chmod(0o644)
            except OSError:  # pragma: no cover - exotic filesystems
                pass
        self.meta.source_path = str(target.resolve())
        return target


def _payload_has_secret(payload: dict[str, Any]) -> bool:
    """Return True when a serialised payload still contains a secret value."""
    for spec in ENV_VAR_SPECS:
        if not spec.secret:
            continue
        node: Any = payload
        for part in spec.path.split("."):
            if not isinstance(node, dict):
                node = None
                break
            node = node.get(part)
        if node:
            return True
    return False


def _assign_dict_path(data: dict[str, Any], path: str, value: Any) -> None:
    """Assign ``value`` at a dotted path inside a plain dictionary."""
    parts = path.split(".")
    node = data
    for part in parts[:-1]:
        child = node.get(part)
        if not isinstance(child, dict):
            return
        node = child
    node[parts[-1]] = value


def _strip_masked_secrets(updates: dict[str, Any]) -> dict[str, Any]:
    """Drop secret fields whose value is the redacted placeholder."""
    cleaned = json.loads(json.dumps(updates))  # deep copy, JSON-safe by construction
    for spec in ENV_VAR_SPECS:
        if not spec.secret:
            continue
        parts = spec.path.split(".")
        node = cleaned
        for part in parts[:-1]:
            child = node.get(part) if isinstance(node, dict) else None
            if not isinstance(child, dict):
                node = None
                break
            node = child
        if not isinstance(node, dict):
            continue
        leaf = parts[-1]
        if leaf in node:
            value = node[leaf]
            if isinstance(value, str) and value.startswith(SECRET_MASK):
                node.pop(leaf)
    return cleaned


# --------------------------------------------------------------------------------------
# Introspection helpers used by the CLI and the visual configurator
# --------------------------------------------------------------------------------------


def env_var_report(config: SynaprConfig | None = None) -> list[dict[str, Any]]:
    """Describe every supported environment variable and its current state."""
    cfg = config or SynaprConfig()
    report: list[dict[str, Any]] = []
    for spec in ENV_VAR_SPECS:
        hit = spec.read()
        try:
            current = get_by_path(cfg, spec.path)
        except KeyError:  # pragma: no cover - defensive
            current = None
        if spec.secret:
            current = redact_secret(current if isinstance(current, str) else None)
        report.append(
            {
                "name": spec.name,
                "aliases": list(spec.aliases),
                "path": spec.path,
                "kind": spec.kind,
                "secret": spec.secret,
                "description": spec.description,
                "example": spec.example,
                "is_set": hit is not None,
                "set_via": hit[0] if hit else None,
                "effective_value": current,
            }
        )
    return report


def render_env_example() -> str:
    """Render a ready-to-copy ``.env.example`` file documenting every variable."""
    lines = [
        "# ---------------------------------------------------------------------------",
        "# Synapr environment configuration",
        "#",
        "# Copy to `.env` (git-ignored) and uncomment what you need, or configure",
        "# everything visually with `synapr ui` -> Configuration tab.",
        "# Precedence: defaults < synapr.config.json < .env < real environment.",
        "# ---------------------------------------------------------------------------",
        "",
    ]
    current_section = ""
    for spec in ENV_VAR_SPECS:
        section = spec.path.split(".")[0] if "." in spec.path else "general"
        if section != current_section:
            current_section = section
            lines.append(f"# --- {section} " + "-" * max(0, 60 - len(section)))
        if spec.description:
            lines.append(f"# {spec.description}")
        if spec.aliases:
            lines.append(f"# Also accepts: {', '.join(spec.aliases)}")
        lines.append(f"# {spec.name}={spec.example}")
        lines.append("")
    return "\n".join(lines).rstrip("\n") + "\n"


def field_widget(annotation: Any) -> str:
    """Infer the widget type the dashboard should render for a field annotation."""
    origin = get_origin(annotation)
    if origin is not None:
        args = [arg for arg in get_args(annotation) if arg is not type(None)]
        if origin is list:
            return "list"
        if origin is dict:
            return "keyvalue"
        if origin is Literal:
            return "select"
        if args:
            return field_widget(args[0])
    if annotation is bool:
        return "boolean"
    if annotation in (int, float):
        return "number"
    return "text"
