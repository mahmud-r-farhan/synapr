"""Shared defaults and names used by the configuration subsystem."""

ENV_PREFIX = "SYNAPR_"
SECRET_MASK = "••••••••"
SUPPORTED_PROVIDERS: tuple[str, ...] = (
    "mock", "ollama", "openai", "openrouter", "groq", "lmstudio", "vllm"
)
CONFIG_FILENAMES: tuple[str, ...] = ("synapr.config.json", ".synapr/config.json")
TRUTHY_VALUES = {"1", "true", "t", "yes", "y", "on"}
FALSY_VALUES = {"0", "false", "f", "no", "n", "off"}
