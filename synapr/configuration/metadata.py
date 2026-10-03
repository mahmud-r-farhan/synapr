"""Configuration source and override provenance."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ConfigMeta:
    """Provenance information attached to a loaded :class:`SynaprConfig`."""

    source_path: str | None = None
    env_file: str | None = None
    env_overrides: dict[str, str] = field(default_factory=dict)
    pre_env_values: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
