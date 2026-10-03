"""Configuration management for Synapr with Pydantic V2."""

import json
import os
from pathlib import Path

from pydantic import BaseModel, Field


class GatewayConfig(BaseModel):
    """Configuration for local LLM engines and remote gateways."""
    default_provider: str = Field(
        default="mock",
        description="Active provider: 'mock', 'ollama', 'openai', 'groq', 'openrouter', 'lmstudio', 'vllm'"
    )
    ollama_base_url: str = Field(default="http://localhost:11434")
    openai_base_url: str = Field(default="https://api.openai.com/v1")
    openai_api_key: str | None = Field(default=None)
    openrouter_api_key: str | None = Field(default=None)
    groq_api_key: str | None = Field(default=None)

    # Models assigned to specific roles
    planner_model: str = Field(default="qwen2.5-coder:7b")
    critic_models: list[str] = Field(default_factory=lambda: ["llama3.2:latest", "mistral:latest"])
    arbiter_model: str = Field(default="qwen2.5-coder:7b")
    resolver_model: str = Field(default="qwen2.5-coder:7b")
    vision_model: str = Field(default="llava:latest")

    timeout_seconds: float = Field(default=60.0)
    temperature: float = Field(default=0.2)
    max_tokens: int = Field(default=4096)


class WorktreeConfig(BaseModel):
    """Configuration for Git worktree directory isolation."""
    worktree_root: str = Field(default=".worktrees")
    base_branch: str = Field(default="master")
    branch_prefix: str = Field(default="synapr/")
    auto_cleanup_on_success: bool = Field(default=False)
    isolate_git_index: bool = Field(default=True)


class EditorConfig(BaseModel):
    """Configuration for IDE detection and dispatch."""
    preferred_editor: str | None = Field(default=None)
    editor_overrides: dict[str, str] = Field(
        default_factory=lambda: {
            "backend": "vscode",
            "frontend": "cursor",
            "android": "android_studio",
            "mobile": "android_studio",
        }
    )
    custom_editor_paths: dict[str, str] = Field(default_factory=dict)
    launch_detached: bool = Field(default=True)


class PerceptionConfig(BaseModel):
    """Configuration for optical screen perception and terminal telemetry."""
    enabled: bool = Field(default=True)
    poll_interval_seconds: float = Field(default=2.5)
    ocr_engine: str = Field(default="auto")  # 'auto', 'tesseract', 'windows_media', 'regex_terminal'
    capture_screenshots: bool = Field(default=True)
    screenshot_dir: str = Field(default=".synapr/screenshots")


class PipelineConfig(BaseModel):
    """Configuration for build, test, and self-healing merge pipeline."""
    auto_test: bool = Field(default=True)
    auto_merge: bool = Field(default=True)
    max_self_healing_attempts: int = Field(default=3)
    default_test_command: str | None = Field(default=None)
    allow_force_merge: bool = Field(default=False)


class SynaprConfig(BaseModel):
    """Root configuration for Synapr local orchestrator."""
    project_name: str = Field(default="Synapr Project")
    gateway: GatewayConfig = Field(default_factory=GatewayConfig)
    worktree: WorktreeConfig = Field(default_factory=WorktreeConfig)
    editor: EditorConfig = Field(default_factory=EditorConfig)
    perception: PerceptionConfig = Field(default_factory=PerceptionConfig)
    pipeline: PipelineConfig = Field(default_factory=PipelineConfig)

    @classmethod
    def load(cls, config_path: str | None = None) -> "SynaprConfig":
        """Load configuration from a file or discover in project/home directories."""
        candidates = [
            Path(config_path) if config_path else None,
            Path("synapr.config.json"),
            Path(".synapr/config.json"),
            Path.home() / ".synapr" / "config.json",
        ]

        for p in candidates:
            if p and p.is_file():
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        return cls.model_validate(data)
                except Exception:
                    pass

        # Environment variable overrides
        cfg = cls()
        if os.getenv("OPENAI_API_KEY"):
            cfg.gateway.openai_api_key = os.getenv("OPENAI_API_KEY")
            if cfg.gateway.default_provider == "mock":
                cfg.gateway.default_provider = "openai"
        if os.getenv("OPENROUTER_API_KEY"):
            cfg.gateway.openrouter_api_key = os.getenv("OPENROUTER_API_KEY")
        if os.getenv("GROQ_API_KEY"):
            cfg.gateway.groq_api_key = os.getenv("GROQ_API_KEY")
        if os.getenv("OLLAMA_BASE_URL"):
            cfg.gateway.ollama_base_url = os.getenv("OLLAMA_BASE_URL")
        return cfg

    def save(self, output_path: str = "synapr.config.json") -> None:
        """Persist configuration to JSON file."""
        target = Path(output_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "w", encoding="utf-8") as f:
            f.write(self.model_dump_json(indent=2))
