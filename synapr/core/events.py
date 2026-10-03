"""Event bus for asynchronous event handling and real-time updates."""

import asyncio
import time
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, Field


class Event(BaseModel):
    """An event emitted during orchestration lifecycle."""
    event_type: str
    data: dict[str, Any] = Field(default_factory=dict)
    timestamp: float = Field(default_factory=time.time)


class EventBus:
    """Thread-safe and async-safe pub/sub event dispatcher."""
    def __init__(self) -> None:
        self._listeners: dict[str, list[Callable[[Event], Any]]] = {}
        self._history: list[Event] = []
        self._max_history: int = 500

    def subscribe(self, event_type: str, callback: Callable[[Event], Any]) -> None:
        """Register a callback for an event type (or '*' for all events)."""
        if event_type not in self._listeners:
            self._listeners[event_type] = []
        self._listeners[event_type].append(callback)

    def unsubscribe(self, event_type: str, callback: Callable[[Event], Any]) -> None:
        """Unregister a previously registered callback."""
        if event_type in self._listeners and callback in self._listeners[event_type]:
            self._listeners[event_type].remove(callback)

    async def emit_async(self, event_type: str, data: dict[str, Any]) -> None:
        """Emit an event asynchronously to all registered listeners."""
        event = Event(event_type=event_type, data=data)
        self._history.append(event)
        if len(self._history) > self._max_history:
            self._history.pop(0)

        targets = self._listeners.get(event_type, []) + self._listeners.get("*", [])
        for cb in targets:
            if asyncio.iscoroutinefunction(cb):
                try:
                    await cb(event)
                except Exception:
                    pass
            else:
                try:
                    cb(event)
                except Exception:
                    pass

    def emit(self, event_type: str, data: dict[str, Any]) -> None:
        """Synchronously emit an event (or schedule if event loop is running)."""
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.emit_async(event_type, data))
        except RuntimeError:
            event = Event(event_type=event_type, data=data)
            self._history.append(event)
            targets = self._listeners.get(event_type, []) + self._listeners.get("*", [])
            for cb in targets:
                if not asyncio.iscoroutinefunction(cb):
                    try:
                        cb(event)
                    except Exception:
                        pass

    def get_history(self, limit: int = 50) -> list[Event]:
        """Return the recent event history."""
        return self._history[-limit:]


# Global event bus singleton
bus = EventBus()
