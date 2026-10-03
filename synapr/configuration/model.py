"""Root Pydantic configuration model and file loading entry point."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import Field, PrivateAttr

from .env_file import load_env_file
from .environment import ConfigEnvironmentMixin
from .metadata import ConfigMeta
from .models import (
    BrowserConfig,
    EditorConfig,
    EmailConfig,
    GatewayConfig,
    GitHubConfig,
    PerceptionConfig,
    PipelineConfig,
    UIConfig,
    WorktreeConfig,
)
from .models.base import _Section
from .paths import discover_config_file
from .serialization import ConfigSerializationMixin


class SynaprConfig(ConfigEnvironmentMixin, ConfigSerializationMixin, _Section):
    """Root configuration for Synapr local orchestrator."""

    project_name: str = Field(default="Synapr Project", description="Project label")
    gateway: GatewayConfig = Field(default_factory=GatewayConfig)
    worktree: WorktreeConfig = Field(default_factory=WorktreeConfig)
    editor: EditorConfig = Field(default_factory=EditorConfig)
    perception: PerceptionConfig = Field(default_factory=PerceptionConfig)
    pipeline: PipelineConfig = Field(default_factory=PipelineConfig)
    ui: UIConfig = Field(default_factory=UIConfig)
    browser: BrowserConfig = Field(default_factory=BrowserConfig)
    email: EmailConfig = Field(default_factory=EmailConfig)
    github: GitHubConfig = Field(default_factory=GitHubConfig)

    _meta: ConfigMeta = PrivateAttr(default_factory=ConfigMeta)

    @property
    def meta(self) -> ConfigMeta:
        """Where this configuration came from (file path, env overrides, errors)."""
        return self._meta

    @meta.setter
    def meta(self, value: ConfigMeta) -> None:
        self._meta = value

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
