"""Server-sent event stream for live dashboard telemetry."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from synapr.core.events import Event, bus

router = APIRouter()


@router.get("/api/events")
async def stream_events(request: Request) -> StreamingResponse:
    """Server-Sent Events (SSE) stream for real-time dashboard telemetry."""

    async def event_generator() -> AsyncGenerator[str, None]:
        q: asyncio.Queue[Event] = asyncio.Queue()

        def _on_event(ev: Event) -> None:
            q.put_nowait(ev)

        bus.subscribe("*", _on_event)
        try:
            # Yield initial connection event
            yield f"event: connected\ndata: {json.dumps({'message': 'Connected to Synapr SSE Stream'})}\n\n"

            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(q.get(), timeout=20.0)
                    yield f"event: {event.event_type}\ndata: {json.dumps(event.data)}\n\n"
                except TimeoutError:
                    # Keep-alive heartbeat ping
                    yield ": ping\n\n"
        finally:
            bus.unsubscribe("*", _on_event)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )
