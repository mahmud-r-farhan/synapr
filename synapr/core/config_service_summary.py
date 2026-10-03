"""Configuration provenance and snapshot payload generation."""

from __future__ import annotations

from typing import Any

from synapr.config import discover_config_file


class ConfigServiceSummaryMixin:
    def summary(self) -> dict[str, Any]:
        """Short provenance summary rendered in the dashboard header."""
        service: Any = self
        cfg = service.config
        discovered = discover_config_file(service._explicit_path, service._base_dir)
        return {
            "source_path": cfg.meta.source_path,
            "target_path": str(service.target_path()),
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
        service: Any = self
        return {"config": service.config.to_dict(redact=redact), "meta": service.summary()}
