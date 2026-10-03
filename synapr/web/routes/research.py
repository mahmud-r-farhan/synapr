"""Web search, clean-page retrieval, and local server inspection endpoints."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter

from synapr.web.models import FetchUrlRequest, LocalhostValidateRequest, SearchRequest
from synapr.web.state import get_orchestrator

router = APIRouter()


@router.get("/api/search")
async def api_search_get(q: str, limit: int = 5) -> dict[str, Any]:
    """Execute live web search for LLM context or user inquiry."""
    from synapr.browser.search import search_web

    results = await asyncio.to_thread(search_web, q, max_results=min(limit, 20))
    return {"query": q, "count": len(results), "results": [r.model_dump() for r in results]}


@router.post("/api/search")
async def api_search_post(req: SearchRequest) -> dict[str, Any]:
    """Search the web and optionally fetch text excerpts from the top pages."""
    gateway = get_orchestrator().gateway
    return await gateway.search_and_research(
        query=req.query, max_results=req.limit, fetch_content=req.fetch_content
    )


@router.post("/api/fetch-url")
async def api_fetch_url(req: FetchUrlRequest) -> dict[str, Any]:
    """Fetch an arbitrary webpage and extract clean markdown text for analysis."""
    from synapr.browser.search import fetch_webpage

    page = await asyncio.to_thread(fetch_webpage, req.url, max_chars=req.max_chars)
    data = page.model_dump()
    data["markdown"] = page.text
    return data


@router.post("/api/browser/validate-localhost")
async def api_validate_localhost(req: LocalhostValidateRequest) -> dict[str, Any]:
    """Inspect local development server health and scan for runtime crash indicators."""
    from synapr.browser.engine import validate_localhost

    result = await asyncio.to_thread(validate_localhost, req.url)
    data = result.model_dump()
    data["is_healthy"] = result.is_healthy
    data["errors_detected"] = result.errors_detected
    return data
