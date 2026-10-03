"""Provider reachability diagnostics and model-list normalization."""

from __future__ import annotations

import time
import urllib.error
from typing import TYPE_CHECKING, Any

from synapr.core.http import request_json

if TYPE_CHECKING:
    from synapr.config import SynaprConfig


class ConfigServiceDiagnosticsMixin:
    if TYPE_CHECKING:
        @property
        def config(self) -> SynaprConfig: ...

    def test_provider(self, provider: str | None = None, timeout: float = 8.0) -> dict[str, Any]:
        """Probe the configured provider endpoint and report reachability."""
        cfg = self.config
        target = (provider or cfg.gateway.default_provider).lower()
        started = time.perf_counter()

        if target == "mock":
            return {
                "provider": target,
                "ok": True,
                "detail": "Deterministic offline engine - always available.",
                "models": [],
                "latency_ms": 0.0,
            }

        if target == "ollama":
            url = f"{cfg.gateway.ollama_base_url.rstrip('/')}/api/tags"
            headers: dict[str, str] = {}
        elif target in {"openai", "openrouter", "groq", "lmstudio", "vllm"}:
            url = f"{cfg.gateway.base_url_for(target).rstrip('/')}/models"
            key = cfg.gateway.api_key_for(target)
            headers = {"Authorization": f"Bearer {key}"} if key else {}
            if target in {"openai", "openrouter", "groq"} and not key:
                return {
                    "provider": target,
                    "ok": False,
                    "detail": "No API key configured for this provider.",
                    "models": [],
                    "latency_ms": 0.0,
                }
        else:
            return {
                "provider": target,
                "ok": False,
                "detail": f"Unknown provider '{target}'. Requests would fall back to mock.",
                "models": [],
                "latency_ms": 0.0,
            }

        try:
            payload = request_json(url, headers=headers, timeout=timeout)
            models = _extract_model_names(payload)
            return {
                "provider": target,
                "ok": True,
                "detail": f"Reachable at {url} ({len(models)} models).",
                "models": models[:50],
                "latency_ms": round((time.perf_counter() - started) * 1000, 1),
            }
        except urllib.error.HTTPError as exc:
            return {
                "provider": target,
                "ok": False,
                "detail": f"HTTP {exc.code} from {url}.",
                "models": [],
                "latency_ms": round((time.perf_counter() - started) * 1000, 1),
            }
        except Exception as exc:
            return {
                "provider": target,
                "ok": False,
                "detail": f"Unreachable: {exc}",
                "models": [],
                "latency_ms": round((time.perf_counter() - started) * 1000, 1),
            }


def _extract_model_names(payload: Any) -> list[str]:
    """Normalise the various /models and /api/tags response shapes."""
    names: list[str] = []
    if isinstance(payload, dict):
        entries = payload.get("models") or payload.get("data") or []
        if isinstance(entries, list):
            for entry in entries:
                if isinstance(entry, dict):
                    name = entry.get("name") or entry.get("id") or entry.get("model")
                    if isinstance(name, str):
                        names.append(name)
                elif isinstance(entry, str):
                    names.append(entry)
    return names
