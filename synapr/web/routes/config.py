"""Read, update, and diagnose dashboard configuration."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse

from synapr.config import render_env_example
from synapr.core.config_service import ConfigServiceError, get_config_service
from synapr.web.models import (
    ConfigUpdateRequest,
    ConfigValueRequest,
    EnvUpdateRequest,
    ProviderTestRequest,
)
from synapr.web.state import _config_lock, get_orchestrator

router = APIRouter()


def _guard_writes() -> None:
    """Reject mutations when the operator disabled dashboard configuration writes."""
    if not get_config_service().config.ui.allow_config_writes:
        raise HTTPException(
            status_code=403,
            detail="Configuration editing is disabled (ui.allow_config_writes = false).",
        )


@router.get("/api/config")
async def read_config() -> dict[str, Any]:
    """Return the active configuration with secrets redacted, plus provenance metadata."""
    return get_config_service().snapshot(redact=True)


@router.get("/api/config/schema")
async def config_schema() -> dict[str, Any]:
    """Return a declarative form description so the dashboard can render every field."""
    orch = get_orchestrator()
    editor_ids = [editor.id for editor in orch.get_installed_editors()]
    return get_config_service().schema(editor_ids=editor_ids)


@router.put("/api/config")
async def update_config(req: ConfigUpdateRequest) -> dict[str, Any]:
    """Validate and apply a partial configuration update, optionally persisting it."""
    _guard_writes()
    service = get_config_service()
    async with _config_lock:
        try:
            await asyncio.to_thread(service.update, req.config, persist=req.persist)
        except ConfigServiceError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except OSError as exc:
            raise HTTPException(status_code=500, detail=f"Failed to persist: {exc}") from exc
    return service.snapshot(redact=True)


@router.post("/api/config/value")
async def set_config_value(req: ConfigValueRequest) -> dict[str, Any]:
    """Set a single configuration field by dotted path."""
    _guard_writes()
    service = get_config_service()
    async with _config_lock:
        try:
            await asyncio.to_thread(service.set_value, req.path, req.value, persist=req.persist)
        except ConfigServiceError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    return service.snapshot(redact=True)


@router.post("/api/config/reset")
async def reset_config(persist: bool = False) -> dict[str, Any]:
    """Restore built-in defaults (environment variables are re-applied on top)."""
    _guard_writes()
    service = get_config_service()
    async with _config_lock:
        await asyncio.to_thread(service.reset, persist=persist)
    return service.snapshot(redact=True)


@router.post("/api/config/reload")
async def reload_config() -> dict[str, Any]:
    """Discard in-memory changes and reload the configuration file from disk."""
    service = get_config_service()
    async with _config_lock:
        await asyncio.to_thread(service.reload)
    return service.snapshot(redact=True)


@router.post("/api/config/save")
async def save_config() -> dict[str, Any]:
    """Persist the in-memory configuration to the project configuration file."""
    _guard_writes()
    service = get_config_service()
    async with _config_lock:
        try:
            path = await asyncio.to_thread(service.persist)
        except OSError as exc:
            raise HTTPException(status_code=500, detail=f"Failed to persist: {exc}") from exc
    return {"status": "saved", "path": str(path), **service.snapshot(redact=True)}


@router.get("/api/config/env")
async def read_env() -> dict[str, Any]:
    """List every supported environment variable with its current state."""
    service = get_config_service()
    return {"variables": service.env_report(), "meta": service.summary()}


@router.post("/api/config/env")
async def write_env(req: EnvUpdateRequest) -> dict[str, Any]:
    """Declare environment variables at runtime and optionally store them in ``.env``."""
    _guard_writes()
    service = get_config_service()
    async with _config_lock:
        try:
            await asyncio.to_thread(
                service.apply_env_values,
                req.values,
                persist_to_env_file=req.persist,
                env_file=req.env_file,
                remove=req.unset,
            )
        except ConfigServiceError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except OSError as exc:
            raise HTTPException(status_code=500, detail=f"Failed to write env file: {exc}") from exc
    return {"variables": service.env_report(), **service.snapshot(redact=True)}


@router.get("/api/config/env/example", response_class=PlainTextResponse)
async def env_example() -> str:
    """Download a documented ``.env.example`` describing every variable."""
    return render_env_example()


@router.post("/api/config/test-provider")
async def test_provider(req: ProviderTestRequest) -> dict[str, Any]:
    """Probe an LLM provider endpoint and report reachability and available models."""
    service = get_config_service()
    return await asyncio.to_thread(service.test_provider, req.provider)
