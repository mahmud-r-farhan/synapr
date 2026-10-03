"""Environment-variable operations for the runtime configuration service."""

from __future__ import annotations

import os
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

from synapr.config import (
    ENV_SPECS_BY_PATH,
    ConfigMeta,
    SynaprConfig,
    env_var_report,
    load_env_file,
    write_env_file,
)
from synapr.core.config_service_support import ConfigServiceError
from synapr.core.events import bus
from synapr.core.logger import logger


class ConfigServiceEnvironmentMixin:
    _base_dir: Path
    _config: SynaprConfig
    _lock: Any
    _notify: Callable[[], None]

    def env_report(self) -> list[dict[str, Any]]:
        """Describe every supported environment variable and whether it is active."""
        service: Any = self
        return env_var_report(service.config)

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
