"""Core environment variable declarations."""

from .constants import SUPPORTED_PROVIDERS
from .env_types import EnvVarSpec

SPECS: tuple[EnvVarSpec, ...] = (
    EnvVarSpec(
        name="SYNAPR_PROJECT_NAME",
        path="project_name",
        description="Human readable project label shown in the dashboard.",
        example="Synapr Swarm",
    ),
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
    )
)
