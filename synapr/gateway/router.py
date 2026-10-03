"""Gateway router managing model assignments and privacy boundaries."""

from synapr.config import GatewayConfig
from synapr.gateway.client import GatewayResponse, LLMGateway


class ModelRouter:
    """Routes requests to the designated model for each cognitive role."""

    def __init__(self, config: GatewayConfig | None = None) -> None:
        self.config = config or GatewayConfig()
        self.gateway = LLMGateway(self.config)

    async def run_planner(self, prompt: str, system_prompt: str | None = None) -> GatewayResponse:
        """Query the designated planner model."""
        return await self.gateway.complete(
            prompt=prompt,
            system_prompt=system_prompt,
            model=self.config.planner_model,
        )

    async def run_critic(
        self, prompt: str, critic_idx: int = 0, system_prompt: str | None = None
    ) -> GatewayResponse:
        """Query one of the configured peer critic models."""
        models = self.config.critic_models or [self.config.planner_model]
        model = models[critic_idx % len(models)]
        return await self.gateway.complete(
            prompt=prompt,
            system_prompt=system_prompt,
            model=model,
        )

    async def run_arbiter(self, prompt: str, system_prompt: str | None = None) -> GatewayResponse:
        """Query the arbiter model for consensus synthesis."""
        return await self.gateway.complete(
            prompt=prompt,
            system_prompt=system_prompt,
            model=self.config.arbiter_model,
        )

    async def run_resolver(self, prompt: str, system_prompt: str | None = None) -> GatewayResponse:
        """Query the resolver model for merge conflict auto-healing."""
        return await self.gateway.complete(
            prompt=prompt,
            system_prompt=system_prompt,
            model=self.config.resolver_model,
        )
