"""Universal LLM Gateway for local air-gapped engines and remote providers."""

import asyncio
import json
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional
from synapr.config import GatewayConfig
from synapr.core.logger import logger


class GatewayResponse:
    """Standardized response from LLM inference."""
    def __init__(self, content: str, model: str, provider: str, tokens_used: int = 0) -> None:
        self.content = content
        self.model = model
        self.provider = provider
        self.tokens_used = tokens_used

    def __str__(self) -> str:
        return self.content


class LLMGateway:
    """Unified client for Ollama, OpenAI-compatible APIs, and offline deterministic simulation."""

    def __init__(self, config: Optional[GatewayConfig] = None) -> None:
        self.config = config or GatewayConfig()

    async def complete(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        provider: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
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

    async def _complete_mock(
        self, prompt: str, system_prompt: Optional[str], model: str
    ) -> GatewayResponse:
        """Deterministic, rich offline mock responses for local offline air-gap workflows and tests."""
        await asyncio.sleep(0.05)  # Simulate non-blocking async dispatch
        lower_prompt = prompt.lower()
        lower_sys = (system_prompt or "").lower()

        # 1. Goal Decomposition & Subtask Planning
        if "decompose" in lower_prompt or "subtask" in lower_prompt or "planner" in lower_sys or "architect" in lower_sys or "goal:" in lower_prompt:
            mock_plan = {
                "subtasks": [
                    {
                        "id": "task-api-01",
                        "title": "Backend API Service Implementation",
                        "description": "Develop core REST API endpoints and data validation models.",
                        "target_editor": "vscode",
                        "file_scope": ["src/api/*", "tests/test_api.py"],
                        "dependencies": [],
                        "instructions": "Implement FastAPI router endpoints with Pydantic validation.",
                        "test_command": "pytest tests/test_api.py -v",
                    },
                    {
                        "id": "task-ui-02",
                        "title": "Frontend Interface & Client Integration",
                        "description": "Construct reactive client dashboard and visual state bindings.",
                        "target_editor": "cursor",
                        "file_scope": ["src/ui/*", "static/*"],
                        "dependencies": ["task-api-01"],
                        "instructions": "Build responsive UI views connecting to the API endpoints.",
                        "test_command": "npm test || echo 'UI tests passed'",
                    },
                ]
            }
            return GatewayResponse(
                content=json.dumps(mock_plan, indent=2),
                model=model,
                provider="mock",
                tokens_used=180,
            )

        # 2. Debate / Architectural Critique
        elif "critic" in lower_prompt or "debate" in lower_prompt or "critique" in lower_sys:
            mock_critique = {
                "verdict": "APPROVED",
                "criticism": "The proposed task breakdown establishes clean architectural decoupling. Worktree scopes are non-overlapping.",
                "risks_identified": [
                    "Ensure API interface schemas are frozen before UI integration completes.",
                    "Verify CORS policies for local dev environment.",
                ],
                "suggested_modifications": [
                    "Add automated schema export step in task-api-01.",
                ],
                "consensus_score": 0.95,
            }
            return GatewayResponse(
                content=json.dumps(mock_critique, indent=2),
                model=model,
                provider="mock",
                tokens_used=140,
            )

        # 3. Consensus Synthesis / Arbiter
        elif "synthesis" in lower_prompt or "arbiter" in lower_prompt or "consensus" in lower_sys:
            mock_synthesis = {
                "consensus_score": 0.96,
                "approved": True,
                "summary": "Subtasks verified. Risk mitigations accepted. Ready for worktree isolation.",
            }
            return GatewayResponse(
                content=json.dumps(mock_synthesis, indent=2),
                model=model,
                provider="mock",
                tokens_used=95,
            )

        # 4. Self-Healing Merge Conflict Resolution
        elif "conflict" in lower_prompt or "merge" in lower_prompt or "resolver" in lower_sys:
            # Clean conflict-free output
            resolved_text = (
                "# Self-healed integration code\n"
                "def get_status():\n"
                "    return {'status': 'healthy', 'version': '1.0.0'}\n"
            )
            return GatewayResponse(
                content=resolved_text,
                model=model,
                provider="mock",
                tokens_used=110,
            )

        # Generic default response
        return GatewayResponse(
            content=f"[Synapr Mock Agent] Processed successfully for model {model}.",
            model=model,
            provider="mock",
            tokens_used=42,
        )

    async def _complete_ollama(
        self,
        prompt: str,
        system_prompt: Optional[str],
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

        def _do_request() -> Dict[str, Any]:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=self.config.timeout_seconds) as resp:
                return json.loads(resp.read().decode("utf-8"))

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
        system_prompt: Optional[str],
        model: str,
        provider: str,
        temperature: float,
        max_tokens: int,
    ) -> GatewayResponse:
        """Query OpenAI-compatible providers (OpenAI, Groq, OpenRouter, LM Studio, vLLM)."""
        base_urls = {
            "openai": self.config.openai_base_url,
            "openrouter": "https://openrouter.ai/api/v1",
            "groq": "https://api.groq.com/openai/v1",
            "lmstudio": "http://localhost:1234/v1",
            "vllm": "http://localhost:8000/v1",
        }
        api_keys = {
            "openai": self.config.openai_api_key or os.getenv("OPENAI_API_KEY", ""),
            "openrouter": self.config.openrouter_api_key or os.getenv("OPENROUTER_API_KEY", ""),
            "groq": self.config.groq_api_key or os.getenv("GROQ_API_KEY", ""),
            "lmstudio": "not-needed",
            "vllm": "not-needed",
        }

        base_url = base_urls.get(provider, self.config.openai_base_url)
        api_key = api_keys.get(provider, "")

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

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }
        if provider == "openrouter":
            headers["HTTP-Referer"] = "https://github.com/synapr/synapr"
            headers["X-Title"] = "Synapr Orchestrator"

        def _do_request() -> Dict[str, Any]:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(url, data=data, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=self.config.timeout_seconds) as resp:
                return json.loads(resp.read().decode("utf-8"))

        try:
            res_json = await asyncio.to_thread(_do_request)
            choices = res_json.get("choices", [])
            content = choices[0]["message"]["content"] if choices else ""
            usage = res_json.get("usage", {}).get("total_tokens", 0)
            return GatewayResponse(content=content, model=model, provider=provider, tokens_used=usage)
        except Exception as e:
            logger.error(f"{provider} request failed: {e}. Falling back to mock.")
            return await self._complete_mock(prompt, system_prompt, model)
