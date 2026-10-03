"""Shared, lazily initialized orchestrator and route synchronization state."""

from __future__ import annotations

import asyncio
import threading
from typing import Any

from synapr.config import SynaprConfig
from synapr.core.config_service import get_config_service
from synapr.orchestrator import SynaprOrchestrator


class _WebState:
    """Mutable singleton state shared by dashboard routes."""

    def __init__(self) -> None:
        self.orchestrator: SynaprOrchestrator | None = None
        self.bound_service: Any = None
        self.orchestrator_lock = threading.RLock()
        self.config_lock = asyncio.Lock()


_state = _WebState()
_config_lock = _state.config_lock

__all__ = ["_config_lock", "get_orchestrator"]


def _on_config_changed(config: SynaprConfig) -> None:
    """Propagate configuration changes into the live orchestrator."""
    with _state.orchestrator_lock:
        if _state.orchestrator is not None:
            _state.orchestrator.apply_config(config)


def get_orchestrator() -> SynaprOrchestrator:
    """Return the shared orchestrator, rebuilding it if the config service changed."""
    service = get_config_service()
    with _state.orchestrator_lock:
        if _state.orchestrator is None or _state.bound_service is not service:
            _state.orchestrator = SynaprOrchestrator(config=service.config)
            service.subscribe(_on_config_changed)
            _state.bound_service = service
        assert _state.orchestrator is not None
        return _state.orchestrator
