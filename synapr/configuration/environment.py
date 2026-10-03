"""Environment-variable overlay behavior for the root config model."""

from __future__ import annotations

import os
from typing import Any, Self, cast

from pydantic import BaseModel

from .env_registry import ENV_SPECS_BY_PATH, ENV_VAR_SPECS
from .metadata import ConfigMeta
from .values import coerce_env_value, get_by_path, set_by_path


class ConfigEnvironmentMixin:
    def apply_env(
        self,
        environ: dict[str, str] | None = None,
        *,
        meta: ConfigMeta | None = None,
    ) -> Self:
        """Apply every environment variable declared in :data:`ENV_VAR_SPECS`."""
        config: Any = self
        target_meta = meta if meta is not None else config.meta
        env = environ if environ is not None else dict(os.environ)
        provider_explicit = False

        # Revert values whose environment variable disappeared since the last pass,
        # so unsetting a variable in the dashboard restores the file/default value.
        for path, _var in list(target_meta.env_overrides.items()):
            spec = ENV_SPECS_BY_PATH.get(path)
            if spec is not None and spec.read(env) is not None:
                continue
            if path in target_meta.pre_env_values:
                try:
                    set_by_path(cast(BaseModel, self), path, target_meta.pre_env_values.pop(path))
                except Exception as exc:  # pragma: no cover - defensive
                    target_meta.errors.append(f"{path}: {exc}")
            target_meta.env_overrides.pop(path, None)

        for spec in ENV_VAR_SPECS:
            hit = spec.read(env)
            if hit is None:
                continue
            name, raw = hit
            try:
                value = coerce_env_value(spec.kind, raw)
            except Exception as exc:
                target_meta.errors.append(f"{name}: {exc}")
                continue
            try:
                previous = get_by_path(cast(BaseModel, self), spec.path)
                set_by_path(cast(BaseModel, self), spec.path, value)
            except Exception as exc:
                target_meta.errors.append(f"{name}: {exc}")
                continue
            target_meta.env_overrides[spec.path] = name
            target_meta.pre_env_values.setdefault(spec.path, previous)
            if spec.path == "gateway.default_provider":
                provider_explicit = True

        # Legacy convenience: an OpenAI key alone promotes the provider away from mock.
        if (
            not provider_explicit
            and config.gateway.default_provider == "mock"
            and (env.get("OPENAI_API_KEY") or env.get("SYNAPR_OPENAI_API_KEY"))
        ):
            target_meta.pre_env_values.setdefault(
                "gateway.default_provider", config.gateway.default_provider
            )
            config.gateway.default_provider = "openai"
            target_meta.env_overrides["gateway.default_provider"] = (
                "OPENAI_API_KEY" if env.get("OPENAI_API_KEY") else "SYNAPR_OPENAI_API_KEY"
            )

        if meta is None:
            config.meta = target_meta
        return self
