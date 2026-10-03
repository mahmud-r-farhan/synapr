"""DuckDuckGo and SearXNG search adapters."""

from __future__ import annotations

import json
import urllib.parse
import urllib.request

from synapr.browser.models import SearchResult
from synapr.core.logger import logger

from .constants import DEFAULT_USER_AGENT
from .parsers import _DuckDuckGoHTMLParser


def search_duckduckgo(query: str, max_results: int = 5, timeout: float = 12.0) -> list[SearchResult]:
    """Search DuckDuckGo HTML Lite and return structured results without API keys."""
    encoded = urllib.parse.urlencode({"q": query, "b": ""})
    url = f"https://html.duckduckgo.com/html/?{encoded}"

    headers = {
        "User-Agent": DEFAULT_USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            content = resp.read().decode("utf-8", errors="replace")

        parser = _DuckDuckGoHTMLParser()
        parser.feed(content)
        results = parser.results[:max_results]
        if results:
            return results
    except Exception as exc:
        logger.debug(f"DuckDuckGo HTML search failed ({exc}), falling back to Instant Answer API")

    # Fallback: DuckDuckGo Instant Answer API
    try:
        api_url = f"https://api.duckduckgo.com/?q={urllib.parse.quote(query)}&format=json&no_html=1&skip_disambig=1"
        req = urllib.request.Request(api_url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))

        fallback_results: list[SearchResult] = []
        if data.get("AbstractText") and data.get("AbstractURL"):
            fallback_results.append(
                SearchResult(
                    title=data.get("Heading") or query,
                    url=data["AbstractURL"],
                    snippet=data["AbstractText"],
                    source="duckduckgo-instant",
                )
            )
        for topic in data.get("RelatedTopics", []):
            if isinstance(topic, dict) and topic.get("Text") and topic.get("FirstURL"):
                fallback_results.append(
                    SearchResult(
                        title=topic.get("Text", "")[:60] + "...",
                        url=topic["FirstURL"],
                        snippet=topic.get("Text", ""),
                        source="duckduckgo-related",
                    )
                )
            if len(fallback_results) >= max_results:
                break
        return fallback_results
    except Exception as exc:
        logger.warning(f"All DuckDuckGo search methods failed: {exc}")
        return []

def search_searxng(
    query: str,
    base_url: str = "http://localhost:8080",
    max_results: int = 5,
    timeout: float = 10.0,
    searxng_url: str | None = None,
) -> list[SearchResult]:
    """Search a local or remote SearXNG instance."""
    target_url = searxng_url or base_url
    url = f"{target_url.rstrip('/')}/search?q={urllib.parse.quote(query)}&format=json"
    headers = {"User-Agent": DEFAULT_USER_AGENT, "Accept": "application/json"}
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
        results: list[SearchResult] = []
        for item in data.get("results", [])[:max_results]:
            results.append(
                SearchResult(
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    snippet=item.get("content", ""),
                    source="searxng",
                )
            )
        return results
    except Exception as exc:
        logger.warning(f"SearXNG search failed ({base_url}): {exc}")
        return []

def search_web(
    query: str,
    max_results: int = 5,
    engine: str = "duckduckgo",
    searxng_url: str = "",
    timeout: float = 12.0,
) -> list[SearchResult]:
    """Universal search dispatcher supporting DuckDuckGo and SearXNG."""
    query = query.strip()
    if not query:
        return []

    if engine.lower() == "searxng" and searxng_url:
        results = search_searxng(query, base_url=searxng_url, max_results=max_results, timeout=timeout)
        if results:
            return results

    return search_duckduckgo(query, max_results=max_results, timeout=timeout)
