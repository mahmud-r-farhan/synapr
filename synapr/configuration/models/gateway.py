"""LLM provider and model-role configuration."""

from __future__ import annotations

import os
from typing import Any

from pydantic import Field, field_validator

from .base import _Section


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
