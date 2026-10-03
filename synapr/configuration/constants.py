"""Shared defaults and names used by the configuration subsystem."""

ENV_PREFIX = "SYNAPR_"
SECRET_MASK = "••••••••"
SUPPORTED_PROVIDERS: tuple[str, ...] = (
    "mock", "ollama", "openai", "openrouter", "groq", "lmstudio", "vllm"
)
CONFIG_FILENAMES: tuple[str, ...] = ("synapr.config.json", ".synapr/config.json")
_TRUTHY = {"1", "true", "t", "yes", "y", "on"}
_FALSY = {"0", "false", "f", "no", "n", "off"}
