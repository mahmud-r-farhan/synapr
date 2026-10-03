"""Public search and webpage-fetching API with backward-compatible exports."""

from .constants import DEFAULT_USER_AGENT
from .fetch import fetch_webpage
from .parsers import _DuckDuckGoHTMLParser, _HTMLTextExtractor, _unwrap_ddg_url  # noqa: F401
from .search_providers import search_duckduckgo, search_searxng, search_web

__all__ = [
    "DEFAULT_USER_AGENT",
    "fetch_webpage",
    "search_duckduckgo",
    "search_searxng",
    "search_web",
]
