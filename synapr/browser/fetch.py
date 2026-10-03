"""Safe webpage retrieval and plain-text extraction."""

from __future__ import annotations

import urllib.error
import urllib.request

from synapr.browser.models import WebPage
from synapr.core.http import validate_url

from .constants import DEFAULT_USER_AGENT
from .parsers import _HTMLTextExtractor


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
        # validate_url() restricts this outbound request to HTTP(S).
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # nosec B310
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
