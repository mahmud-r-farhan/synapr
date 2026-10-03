"""Universal LLM client for local engines and OpenAI-compatible providers."""

from __future__ import annotations

import asyncio
from typing import Any

from synapr.config import GatewayConfig
from synapr.core.http import request_json
from synapr.core.logger import logger
from synapr.gateway.mock import GatewayMockMixin
from synapr.gateway.models import GatewayResponse
from synapr.gateway.research import GatewayResearchMixin


class LLMGateway(GatewayResearchMixin, GatewayMockMixin):
    """Unified client for local, remote, and deterministic mock providers."""

    def __init__(self, config: GatewayConfig | None = None) -> None:
        self.config = config or GatewayConfig()

    async def complete(
        self,
        prompt: str,
        system_prompt: str | None = None,
        model: str | None = None,
        provider: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> GatewayResponse:
        """Execute a text completion or chat prompt across the active provider."""
        active_provider = (provider or self.config.default_provider).lower()
        active_model = model or self.config.planner_model
        temp = temperature if temperature is not None else self.config.temperature
        tokens = max_tokens or self.config.max_tokens

        logger.debug(f"LLM Request: provider={active_provider} model={active_model}")

        if active_provider == "mock":
            return await self._complete_mock(prompt, system_prompt, active_model)
        elif active_provider == "ollama":
            return await self._complete_ollama(prompt, system_prompt, active_model, temp, tokens)
        elif active_provider in ["openai", "openrouter", "groq", "lmstudio", "vllm"]:
            return await self._complete_openai_compatible(
                prompt, system_prompt, active_model, active_provider, temp, tokens
            )
        else:
            logger.warning(f"Unknown provider '{active_provider}', falling back to mock")
            return await self._complete_mock(prompt, system_prompt, active_model)

    async def _complete_ollama(
        self,
        prompt: str,
        system_prompt: str | None,
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> GatewayResponse:
        """Query local air-gapped Ollama instance via HTTP API."""
        url = f"{self.config.ollama_base_url.rstrip('/')}/api/generate"
        payload = {
            "model": model,
            "prompt": prompt,
            "system": system_prompt or "",
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }

        def _do_request() -> dict[str, Any]:
            result = request_json(
                url, method="POST", payload=payload, timeout=self.config.timeout_seconds
            )
            return result if isinstance(result, dict) else {}

        try:
            res_json = await asyncio.to_thread(_do_request)
            content = res_json.get("response", "")
            tokens = res_json.get("eval_count", 0)
            return GatewayResponse(content=content, model=model, provider="ollama", tokens_used=tokens)
        except Exception as e:
            logger.error(f"Ollama inference failed: {e}. Falling back to mock engine.")
            return await self._complete_mock(prompt, system_prompt, model)

    async def _complete_openai_compatible(
        self,
        prompt: str,
        system_prompt: str | None,
        model: str,
        provider: str,
        temperature: float,
        max_tokens: int,
    ) -> GatewayResponse:
        """Query OpenAI-compatible providers (OpenAI, Groq, OpenRouter, LM Studio, vLLM)."""
        # Endpoints and credentials are fully configurable (config file, env vars
        # or the visual configurator) - see synapr.config.GatewayConfig.
        base_url = self.config.base_url_for(provider)
        api_key = self.config.api_key_for(provider)

        url = f"{base_url.rstrip('/')}/chat/completions"
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        headers = {"Authorization": f"Bearer {api_key}"}
        if provider == "openrouter":
            headers["HTTP-Referer"] = "https://github.com/synapr/synapr"
            headers["X-Title"] = "Synapr Orchestrator"

        def _do_request() -> dict[str, Any]:
            result = request_json(
                url,
                method="POST",
                payload=payload,
                headers=headers,
                timeout=self.config.timeout_seconds,
            )
            return result if isinstance(result, dict) else {}

        try:
            res_json = await asyncio.to_thread(_do_request)
            choices = res_json.get("choices", [])
            content = choices[0]["message"]["content"] if choices else ""
            usage = res_json.get("usage", {}).get("total_tokens", 0)
            return GatewayResponse(content=content, model=model, provider=provider, tokens_used=usage)
        except Exception as e:
            logger.error(f"{provider} request failed: {e}. Falling back to mock.")
            return await self._complete_mock(prompt, system_prompt, model)
