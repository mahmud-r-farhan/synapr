"""Web search and URL content fetching engine with zero required API keys.

Provides DuckDuckGo HTML scraping, DuckDuckGo Instant Answer API queries,
SearXNG integration, and robust HTML-to-text/Markdown extraction for LLM prompts.
"""

from __future__ import annotations

import html
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser

from synapr.browser.models import SearchResult, WebPage
from synapr.core.http import validate_url
from synapr.core.logger import logger

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)


class _HTMLTextExtractor(HTMLParser):
    """Clean HTML parser that strips scripts, styles, and produces readable markdown."""

    def __init__(self) -> None:
        super().__init__()
        self.text_parts: list[str] = []
        self.title_parts: list[str] = []
        self.in_script_or_style = False
        self.in_title = False
        self.links: list[dict[str, str]] = []
        self._current_href: str | None = None
        self._current_link_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "svg", "noscript", "iframe"}:
            self.in_script_or_style = True
        elif tag == "title":
            self.in_title = True
        elif tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            self.text_parts.append("\n\n### ")
        elif tag in {"p", "div", "section", "article", "tr", "li"}:
            self.text_parts.append("\n")
        elif tag == "a":
            href = dict(attrs).get("href")
            if href and not href.startswith(("#", "javascript:")):
                self._current_href = href
                self._current_link_text = []

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "svg", "noscript", "iframe"}:
            self.in_script_or_style = False
        elif tag == "title":
            self.in_title = False
        elif tag in {"h1", "h2", "h3", "h4", "h5", "h6", "p"}:
            self.text_parts.append("\n")
        elif tag == "a" and self._current_href:
            link_text = "".join(self._current_link_text).strip()
            if link_text:
                self.links.append({"text": link_text, "url": self._current_href})
            self._current_href = None
            self._current_link_text = []

    def handle_data(self, data: str) -> None:
        if self.in_script_or_style:
            return
        if self.in_title:
            self.title_parts.append(data)
            return
        if self._current_href is not None:
            self._current_link_text.append(data)
        self.text_parts.append(data)

    def get_text(self) -> str:
        raw = "".join(self.text_parts)
        # Collapse excessive whitespace and blank lines
        lines = [re.sub(r"[ \t]+", " ", line).strip() for line in raw.splitlines()]
        cleaned = "\n".join(line for line in lines if line)
        return html.unescape(cleaned)

    def get_title(self) -> str:
        return html.unescape("".join(self.title_parts)).strip()


class _DuckDuckGoHTMLParser(HTMLParser):
    """Extract organic search results from DuckDuckGo HTML Lite."""

    def __init__(self) -> None:
        super().__init__()
        self.results: list[SearchResult] = []
        self._current_title: list[str] = []
        self._current_url: str = ""
        self._current_snippet: list[str] = []
        self._capture_title = False
        self._capture_snippet = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        attr_dict = {k.lower(): v for k, v in attrs if v is not None}
        cls = attr_dict.get("class", "")

        if tag == "a" and ("result__snippet" in cls or "result__title" in cls or "result__url" in cls or "result-link" in cls):
            href = attr_dict.get("href", "")
            # DuckDuckGo wraps URLs in //duckduckgo.com/l/?uddg=<url>&...
            actual_url = _unwrap_ddg_url(href)
            if actual_url:
                self._current_url = actual_url
            self._capture_title = True
            self._current_title = []
        elif "result__snippet" in cls:
            self._capture_snippet = True
            self._current_snippet = []

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag == "a" and self._capture_title:
            self._capture_title = False
            title = "".join(self._current_title).strip()
            if self._current_url and title:
                self.results.append(
                    SearchResult(
                        title=html.unescape(title) or self._current_url,
                        url=self._current_url,
                        snippet="",
                        source="duckduckgo",
                    )
                )
                self._current_url = ""
                self._current_title = []
        elif self._capture_snippet and tag in {"td", "div", "p", "a", "span"}:
            self._capture_snippet = False
            snippet = "".join(self._current_snippet).strip()
            if self.results and not self.results[-1].snippet:
                self.results[-1].snippet = html.unescape(snippet)
            elif self._current_url:
                title = "".join(self._current_title).strip()
                self.results.append(
                    SearchResult(
                        title=html.unescape(title) or self._current_url,
                        url=self._current_url,
                        snippet=html.unescape(snippet),
                        source="duckduckgo",
                    )
                )
                self._current_url = ""
                self._current_title = []
                self._current_snippet = []

    def handle_data(self, data: str) -> None:
        if self._capture_title:
            self._current_title.append(data)
        elif self._capture_snippet:
            self._current_snippet.append(data)


def _unwrap_ddg_url(raw_href: str) -> str:
    """Extract real destination URL from DuckDuckGo redirect link."""
    if not raw_href:
        return ""
    if raw_href.startswith("/"):
        parsed = urllib.parse.urlparse(raw_href)
        params = urllib.parse.parse_qs(parsed.query)
        if "uddg" in params and params["uddg"]:
            return params["uddg"][0]
    elif raw_href.startswith("http"):
        return raw_href
    return ""


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


def fetch_webpage(url: str, max_chars: int = 12000, timeout: float = 15.0) -> WebPage:
    """Fetch an arbitrary webpage and extract clean markdown text for LLM consumption."""
    try:
        validate_url(url)
    except Exception as exc:
        return WebPage(url=url, error=str(exc), status_code=400)

    headers = {
        "User-Agent": DEFAULT_USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,text/plain;q=0.9,*/*;q=0.8",
    }

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status_code = resp.getcode()
            content = resp.read().decode("utf-8", errors="replace")

        extractor = _HTMLTextExtractor()
        extractor.feed(content)
        text = extractor.get_text()
        if len(text) > max_chars:
            text = text[:max_chars] + f"\n\n... [Truncated: {len(text) - max_chars} characters omitted]"

        return WebPage(
            url=url,
            title=extractor.get_title() or url,
            text=text,
            status_code=status_code,
            content_length=len(content),
            links=extractor.links[:25],
        )
    except urllib.error.HTTPError as exc:
        return WebPage(url=url, status_code=exc.code, error=f"HTTP {exc.code}: {exc.reason}")
    except Exception as exc:
        return WebPage(url=url, status_code=500, error=str(exc))
