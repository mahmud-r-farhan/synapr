"""Web research helpers exposed through the LLM gateway."""

from __future__ import annotations

import asyncio
from typing import Any

from synapr.core.logger import logger


class GatewayResearchMixin:
    async def search_and_research(
        self,
        query: str,
        max_results: int = 5,
        fetch_content: bool = True,
    ) -> dict[str, Any]:
        """Query the search engine and optionally extract content from top results."""
        from synapr.browser.search import fetch_webpage, search_web

        results = await asyncio.to_thread(search_web, query, max_results=max_results)
        pages: list[dict[str, Any]] = []

        if fetch_content and results:
            for item in results[:2]:
                try:
                    page = await asyncio.to_thread(fetch_webpage, item.url, max_chars=4000)
                    if not page.error and page.text:
                        pages.append({
                            "url": page.url,
                            "title": page.title,
                            "summary": page.text[:1200],
                        })
                except Exception as exc:
                    logger.debug(f"Failed to fetch research page {item.url}: {exc}")

        return {
            "query": query,
            "results_count": len(results),
            "results": [r.model_dump() for r in results],
            "extracted_pages": pages,
        }

    async def research_topic(self, topic: str) -> str:
        """Conduct live web research on a topic and return a formatted markdown brief."""
        data = await self.search_and_research(topic, max_results=3, fetch_content=True)
        lines = [f"### Web Research: {topic}"]
        for res in data["results"]:
            lines.append(f"- **[{res['title']}]({res['url']})**: {res['snippet']}")
        if data["extracted_pages"]:
            lines.append("\n**Key Documentation Excerpts:**")
            for page in data["extracted_pages"]:
                lines.append(f"> *From {page['title']}*:\n> {page['summary'][:400]}...")
        return "\n".join(lines)
