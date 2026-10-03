"""HTML parsers for search results and readable webpage extraction."""

from __future__ import annotations

import html
import re
import urllib.parse
from html.parser import HTMLParser

from synapr.browser.models import SearchResult


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
