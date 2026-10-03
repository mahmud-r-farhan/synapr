"""Runtime configuration service powering the CLI and the visual configurator.

The service owns the *active* :class:`~synapr.config.SynaprConfig` instance, keeps
it consistent across the CLI, the orchestrator and the web dashboard, and exposes
a UI-friendly schema so the dashboard can render a form for every setting without
hardcoding field names.
"""

from __future__ import annotations

import os
import threading
import time
import urllib.error
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any, get_args

from pydantic import BaseModel, ValidationError

from synapr.config import (
    ENV_SPECS_BY_PATH,
    SUPPORTED_PROVIDERS,
    ConfigMeta,
    SynaprConfig,
    coerce_env_value,
    default_config_path,
    discover_config_file,
    env_var_report,
    field_widget,
    get_by_path,
    load_env_file,
    redact_secret,
    set_by_path,
    write_env_file,
)
from synapr.core.events import bus
from synapr.core.http import request_json
from synapr.core.logger import logger

__all__ = [
    "ConfigService",
    "ConfigServiceError",
    "get_config_service",
    "reset_config_service",
    "set_config_service",
]


class ConfigServiceError(Exception):
    """Raised when a configuration mutation cannot be applied."""


SELECT_OPTIONS: dict[str, list[str]] = {
    "gateway.default_provider": list(SUPPORTED_PROVIDERS),
    "perception.ocr_engine": ["auto", "tesseract", "windows_media", "regex_terminal"],
}

SECTION_META: dict[str, dict[str, str]] = {
    "general": {
        "title": "Project",
        "icon": "🧭",
        "description": "Identity of the workspace Synapr is orchestrating.",
    },
    "gateway": {
        "title": "LLM Gateway",
        "icon": "🌐",
        "description": "Local engines and optional remote providers, plus per-role models.",
    },
    "worktree": {
        "title": "Git Worktrees",
        "icon": "🌿",
        "description": "Isolation strategy for parallel agents.",
    },
    "editor": {
        "title": "Editors & Dispatch",
        "icon": "🖥️",
        "description": "How detected IDEs are matched to subtasks and launched.",
    },
    "perception": {
        "title": "Perception",
        "icon": "👁️",
        "description": "Optical window inspection and terminal telemetry.",
    },
    "pipeline": {
        "title": "Test & Merge Pipeline",
        "icon": "🧪",
        "description": "Automated verification and self-healing integration.",
    },
    "ui": {
        "title": "Dashboard",
        "icon": "🎛️",
        "description": "Local control center behaviour and safety switches.",
    },
}


def _constraints(field_info: Any) -> dict[str, Any]:
    """Extract numeric constraints (ge/gt/le/lt) from a pydantic FieldInfo."""
    out: dict[str, Any] = {}
    for item in getattr(field_info, "metadata", []) or []:
        for attr, key in (("ge", "min"), ("gt", "exclusive_min"), ("le", "max"), ("lt", "exclusive_max")):
            value = getattr(item, attr, None)
            if value is not None:
                out[key] = value
    return out


def _humanise(name: str) -> str:
    """Turn ``max_self_healing_attempts`` into ``Max Self Healing Attempts``."""
    replacements = {"Url": "URL", "Api": "API", "Ui": "UI", "Ocr": "OCR", "Llm": "LLM"}
    words = [word.capitalize() for word in name.split("_")]
    return " ".join(replacements.get(word, word) for word in words)


class ConfigService:
    """Thread-safe holder and mutator of the active Synapr configuration."""

    def __init__(
        self,
        config: SynaprConfig | None = None,
        *,
        config_path: str | Path | None = None,
        base_dir: str | Path | None = None,
    ) -> None:
        self._lock = threading.RLock()
        self._base_dir = Path(base_dir or ".").resolve()
        self._explicit_path = str(config_path) if config_path else None
        self._listeners: list[Callable[[SynaprConfig], None]] = []
        self._config = config or SynaprConfig.load(self._explicit_path, base_dir=self._base_dir)

    # ------------------------------------------------------------------ accessors
    @property
    def config(self) -> SynaprConfig:
        """Current active configuration instance."""
        with self._lock:
            return self._config

    @property
    def base_dir(self) -> Path:
        """Directory used to resolve relative config/env file paths."""
        return self._base_dir

    def target_path(self) -> Path:
        """File path that :meth:`persist` would write to."""
        source = self._config.meta.source_path
        if source:
            return Path(source)
        if self._explicit_path:
            return Path(self._explicit_path)
        return default_config_path(self._base_dir)

    def subscribe(self, callback: Callable[[SynaprConfig], None]) -> None:
        """Register a callback invoked whenever the active configuration changes."""
        with self._lock:
            self._listeners.append(callback)

    def _notify(self) -> None:
        for callback in list(self._listeners):
            try:
                callback(self._config)
            except Exception as exc:  # pragma: no cover - listener must never break writes
                logger.error(f"Configuration listener failed: {exc}")

    # ------------------------------------------------------------------ mutations
    def set_config(self, config: SynaprConfig, *, reason: str = "replace") -> SynaprConfig:
        """Replace the active configuration and notify subscribers."""
        with self._lock:
            self._config = config
            self._notify()
        bus.emit("config:updated", {"reason": reason, "provider": config.gateway.default_provider})
        return config

    def reload(self, config_path: str | Path | None = None) -> SynaprConfig:
        """Re-read the configuration file and environment from disk."""
        path = str(config_path) if config_path else self._explicit_path
        cfg = SynaprConfig.load(path, base_dir=self._base_dir)
        return self.set_config(cfg, reason="reload")

    def update(
        self,
        updates: dict[str, Any],
        *,
        persist: bool = True,
        config_path: str | Path | None = None,
    ) -> SynaprConfig:
        """Deep-merge a partial configuration payload, validate and optionally persist."""
        if not isinstance(updates, dict):
            raise ConfigServiceError("Configuration updates must be a JSON object")
        with self._lock:
            try:
                new_cfg = self._config.apply_updates(updates)
            except ValidationError as exc:
                raise ConfigServiceError(_format_validation_error(exc)) from exc
            except Exception as exc:
                raise ConfigServiceError(str(exc)) from exc

            self._config = new_cfg
            if persist:
                self._persist_locked(config_path)
            self._notify()
        bus.emit(
            "config:updated",
            {"reason": "update", "persisted": persist, "provider": new_cfg.gateway.default_provider},
        )
        return new_cfg

    def set_value(self, path: str, raw_value: Any, *, persist: bool = True) -> SynaprConfig:
        """Set a single dotted-path value, coercing strings to the declared type."""
        spec = ENV_SPECS_BY_PATH.get(path)
        value = raw_value
        if isinstance(raw_value, str) and spec is not None:
            try:
                value = coerce_env_value(spec.kind, raw_value)
            except Exception as exc:
                raise ConfigServiceError(f"{path}: {exc}") from exc
        with self._lock:
            candidate = self._config.model_copy(deep=True)
            try:
                set_by_path(candidate, path, value)
            except KeyError as exc:
                raise ConfigServiceError(f"Unknown configuration path: {path}") from exc
            except ValidationError as exc:
                raise ConfigServiceError(_format_validation_error(exc)) from exc
            candidate.meta = ConfigMeta(
                source_path=self._config.meta.source_path,
                env_file=self._config.meta.env_file,
                env_overrides=dict(self._config.meta.env_overrides),
                pre_env_values=dict(self._config.meta.pre_env_values),
            )
            self._config = candidate
            if persist:
                self._persist_locked(None)
            self._notify()
        bus.emit("config:updated", {"reason": "set", "path": path})
        return self._config

    def reset(self, *, persist: bool = False) -> SynaprConfig:
        """Restore built-in defaults (environment overrides are re-applied)."""
        with self._lock:
            fresh = SynaprConfig()
            fresh.apply_env()
            fresh.meta.source_path = self._config.meta.source_path
            self._config = fresh
            if persist:
                self._persist_locked(None)
            self._notify()
        bus.emit("config:updated", {"reason": "reset"})
        return self._config

    def persist(self, config_path: str | Path | None = None) -> Path:
        """Write the active configuration to disk atomically."""
        with self._lock:
            return self._persist_locked(config_path)

    def _persist_locked(self, config_path: str | Path | None) -> Path:
        target = Path(config_path) if config_path else self.target_path()
        written = self._config.save(target)
        logger.info(f"Configuration persisted to {written}")
        return written

    # ------------------------------------------------------------------ environment
    def env_report(self) -> list[dict[str, Any]]:
        """Describe every supported environment variable and whether it is active."""
        return env_var_report(self.config)

    def apply_env_values(
        self,
        values: dict[str, str],
        *,
        persist_to_env_file: bool = False,
        env_file: str | Path = ".env",
        remove: Iterable[str] | None = None,
    ) -> SynaprConfig:
        """Set environment variables for this process and re-apply them to the config.

        This is what powers *“declare env variables visually, after the run”*: the
        dashboard can inject a key, Synapr exports it to :data:`os.environ`, applies
        it to the live configuration and (optionally) stores it in a git-ignored
        ``.env`` file so the next run picks it up automatically.
        """
        removals = list(remove or [])
        known = {name for spec in ENV_SPECS_BY_PATH.values() for name in spec.names}
        unknown = [key for key in values if not key.startswith("SYNAPR_") and key not in known]
        if unknown:
            raise ConfigServiceError(
                "Refusing to set non-Synapr environment variables: " + ", ".join(sorted(unknown))
            )

        for key, value in values.items():
            os.environ[key] = str(value)
        for key in removals:
            os.environ.pop(key, None)

        if persist_to_env_file:
            path = Path(env_file)
            if not path.is_absolute():
                path = self._base_dir / path
            write_env_file({k: str(v) for k, v in values.items()}, path, remove=removals)
            logger.info(f"Environment variables persisted to {path}")

        with self._lock:
            refreshed = self._config.model_copy(deep=True)
            refreshed.meta = ConfigMeta(
                source_path=self._config.meta.source_path,
                env_file=self._config.meta.env_file,
                env_overrides=dict(self._config.meta.env_overrides),
                pre_env_values=dict(self._config.meta.pre_env_values),
            )
            refreshed.apply_env()
            self._config = refreshed
            self._notify()
        bus.emit("config:updated", {"reason": "env", "keys": sorted(values)})
        return self._config

    def load_env_file(self, env_file: str | Path = ".env", override: bool = False) -> dict[str, str]:
        """Load a ``.env`` file then re-apply the environment to the live config."""
        path = Path(env_file)
        if not path.is_absolute():
            path = self._base_dir / path
        loaded = load_env_file(path, override=override)
        if loaded:
            with self._lock:
                self._config.apply_env()
                self._notify()
        return loaded

    # ------------------------------------------------------------------ introspection
    def schema(self, editor_ids: list[str] | None = None) -> dict[str, Any]:
        """Return a declarative form description for the visual configurator."""
        cfg = self.config
        env_overrides = cfg.meta.env_overrides
        sections: list[dict[str, Any]] = []

        general_fields: list[dict[str, Any]] = []
        for name, field_info in SynaprConfig.model_fields.items():
            annotation = field_info.annotation
            if isinstance(annotation, type) and issubclass(annotation, BaseModel):
                continue
            general_fields.append(
                self._describe_field(cfg, name, name, field_info, env_overrides, editor_ids)
            )
        if general_fields:
            sections.append({"key": "general", **SECTION_META["general"], "fields": general_fields})

        for section_name, section_field in SynaprConfig.model_fields.items():
            annotation = section_field.annotation
            if not (isinstance(annotation, type) and issubclass(annotation, BaseModel)):
                continue
            fields = [
                self._describe_field(
                    cfg,
                    f"{section_name}.{field_name}",
                    field_name,
                    field_info,
                    env_overrides,
                    editor_ids,
                )
                for field_name, field_info in annotation.model_fields.items()
            ]
            meta = SECTION_META.get(section_name, {"title": _humanise(section_name), "icon": "⚙️"})
            sections.append({"key": section_name, **meta, "fields": fields})

        return {
            "sections": sections,
            "providers": list(SUPPORTED_PROVIDERS),
            "env_prefix": "SYNAPR_",
        }

    def _describe_field(
        self,
        cfg: SynaprConfig,
        path: str,
        name: str,
        field_info: Any,
        env_overrides: dict[str, str],
        editor_ids: list[str] | None,
    ) -> dict[str, Any]:
        spec = ENV_SPECS_BY_PATH.get(path)
        widget = field_widget(field_info.annotation)
        options: list[str] | None = None

        literal_args = [arg for arg in get_args(field_info.annotation) if isinstance(arg, str)]
        if widget == "select" and literal_args:
            options = literal_args
        if path in SELECT_OPTIONS:
            widget, options = "select", list(SELECT_OPTIONS[path])
        if path == "editor.preferred_editor" and editor_ids:
            widget, options = "select", ["", *editor_ids]
        if spec is not None and spec.secret:
            widget = "password"

        try:
            value = get_by_path(cfg, path)
        except KeyError:  # pragma: no cover - defensive
            value = None
        if spec is not None and spec.secret:
            value = redact_secret(value if isinstance(value, str) else None)

        descriptor: dict[str, Any] = {
            "path": path,
            "name": name,
            "label": _humanise(name),
            "widget": widget,
            "nullable": type(None) in get_args(field_info.annotation),
            "help": field_info.description or (spec.description if spec else ""),
            "value": value,
            "secret": bool(spec and spec.secret),
            "env": spec.name if spec else None,
            "env_aliases": list(spec.aliases) if spec else [],
            "env_locked": path in env_overrides,
            "env_locked_by": env_overrides.get(path),
            "placeholder": spec.example if spec else "",
        }
        if options is not None:
            descriptor["options"] = options
        descriptor.update(_constraints(field_info))
        return descriptor

    def summary(self) -> dict[str, Any]:
        """Short provenance summary rendered in the dashboard header."""
        cfg = self.config
        discovered = discover_config_file(self._explicit_path, self._base_dir)
        return {
            "source_path": cfg.meta.source_path,
            "target_path": str(self.target_path()),
            "config_file_exists": discovered is not None,
            "env_file": cfg.meta.env_file,
            "env_overrides": dict(cfg.meta.env_overrides),
            "errors": list(cfg.meta.errors),
            "secrets": cfg.secret_status(),
            "provider": cfg.gateway.default_provider,
            "local_only": cfg.gateway.is_local_provider,
            "writes_allowed": cfg.ui.allow_config_writes,
        }

    def snapshot(self, *, redact: bool = True) -> dict[str, Any]:
        """Full payload consumed by ``GET /api/config``."""
        return {"config": self.config.to_dict(redact=redact), "meta": self.summary()}

    # ------------------------------------------------------------------ diagnostics
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


def _format_validation_error(exc: ValidationError) -> str:
    """Render a pydantic validation error as a compact, user-facing message."""
    parts = []
    for error in exc.errors():
        location = ".".join(str(item) for item in error.get("loc", ()))
        parts.append(f"{location or 'config'}: {error.get('msg', 'invalid value')}")
    return "; ".join(parts) or str(exc)


_service: ConfigService | None = None


def get_config_service(
    *,
    config_path: str | Path | None = None,
    base_dir: str | Path | None = None,
    refresh: bool = False,
) -> ConfigService:
    """Return the process-wide configuration service, creating it on first use."""
    global _service
    if _service is None or refresh:
        _service = ConfigService(config_path=config_path, base_dir=base_dir)
    return _service


def set_config_service(service: ConfigService) -> ConfigService:
    """Install a specific service instance (used by the CLI and by tests)."""
    global _service
    _service = service
    return _service


def reset_config_service() -> None:
    """Drop the cached service so the next access reloads from disk."""
    global _service
    _service = None


def __getattr__(name: str) -> Any:
    """Expose ``config_service`` as a lazily initialised module attribute."""
    if name == "config_service":
        return get_config_service()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
