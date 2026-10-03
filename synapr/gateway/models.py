"""Normalized completion response shared across provider implementations."""


class GatewayResponse:
    """Standardized response from LLM inference."""
    def __init__(self, content: str, model: str, provider: str, tokens_used: int = 0) -> None:
        self.content = content
        self.model = model
        self.provider = provider
        self.tokens_used = tokens_used

    def __str__(self) -> str:
        return self.content
