"""Public facade for the modular runtime configuration service."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from synapr.core.config_service_diagnostics import (  # noqa: F401
    ConfigServiceDiagnosticsMixin,
    _extract_model_names,
)
from synapr.core.config_service_environment import ConfigServiceEnvironmentMixin
from synapr.core.config_service_runtime import ConfigServiceRuntimeMixin
from synapr.core.config_service_schema import (  # noqa: F401
    SECTION_META,
    SELECT_OPTIONS,
    ConfigServiceSchemaMixin,
    _constraints,
    _humanise,
)
from synapr.core.config_service_summary import ConfigServiceSummaryMixin
from synapr.core.config_service_support import (  # noqa: F401
    ConfigServiceError,
    _format_validation_error,
)

__all__ = [
    "ConfigService",
    "ConfigServiceError",
    "get_config_service",
    "reset_config_service",
    "set_config_service",
]


class ConfigService(
    ConfigServiceRuntimeMixin,
    ConfigServiceEnvironmentMixin,
    ConfigServiceSchemaMixin,
    ConfigServiceSummaryMixin,
    ConfigServiceDiagnosticsMixin,
):
    """Thread-safe holder and mutator of the active Synapr configuration."""


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
    """Expose ``config_service`` as a lazily initialized module attribute."""
    if name == "config_service":
        return get_config_service()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
