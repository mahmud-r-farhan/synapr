"""Browser automation, dev-server verification, and web search research subsystem."""

from synapr.browser.engine import validate_localhost
from synapr.browser.models import LocalhostValidationResult, SearchResult, WebPage
from synapr.browser.search import fetch_webpage, search_duckduckgo, search_searxng, search_web

__all__ = [
    "LocalhostValidationResult",
    "SearchResult",
    "WebPage",
    "fetch_webpage",
    "search_duckduckgo",
    "search_searxng",
    "search_web",
    "validate_localhost",
]
