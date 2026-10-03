"""Active configuration lifecycle, mutation, and persistence methods."""

from __future__ import annotations

import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from synapr.config import (
    ENV_SPECS_BY_PATH,
    ConfigMeta,
    SynaprConfig,
    coerce_env_value,
    default_config_path,
    set_by_path,
)
from synapr.core.config_service_support import ConfigServiceError, _format_validation_error
from synapr.core.events import bus
from synapr.core.logger import logger


class ConfigServiceRuntimeMixin:
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
