"""Configuration provenance and snapshot payload generation."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

from synapr.config import SynaprConfig, discover_config_file


class ConfigServiceSummaryMixin:
    if TYPE_CHECKING:
        @property
        def config(self) -> SynaprConfig: ...

    _explicit_path: str | None
    _base_dir: Path
    target_path: Callable[[], Path]

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
