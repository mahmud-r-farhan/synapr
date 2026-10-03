"""Shared, lazily initialized orchestrator and route synchronization state."""

from __future__ import annotations

import asyncio
import threading
from typing import Any

from synapr.config import SynaprConfig
from synapr.core.config_service import get_config_service
from synapr.orchestrator import SynaprOrchestrator

_orchestrator: SynaprOrchestrator | None = None
_bound_service: Any = None
_orchestrator_lock = threading.RLock()
_config_lock = asyncio.Lock()


def _on_config_changed(config: SynaprConfig) -> None:
    """Propagate configuration changes into the live orchestrator."""
    with _orchestrator_lock:
        if _orchestrator is not None:
            _orchestrator.apply_config(config)


def get_orchestrator() -> SynaprOrchestrator:
    """Return the shared orchestrator, rebuilding it if the config service changed."""
    global _orchestrator, _bound_service
    service = get_config_service()
    with _orchestrator_lock:
        if _orchestrator is None or _bound_service is not service:
            _orchestrator = SynaprOrchestrator(config=service.config)
            service.subscribe(_on_config_changed)
            _bound_service = service
        return _orchestrator
