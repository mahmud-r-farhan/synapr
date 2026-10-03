"""Minimal, dependency-free HTTP helper with a strict scheme allow-list.

Every outbound call in Synapr goes through here so that a misconfigured (or
maliciously crafted) base URL cannot turn an "LLM request" into a local file
read via ``file://`` or an arbitrary custom scheme handler.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

__all__ = ["ALLOWED_SCHEMES", "InsecureURLError", "request_json", "validate_url"]

ALLOWED_SCHEMES = frozenset({"http", "https"})


class InsecureURLError(ValueError):
    """Raised when a URL uses a scheme Synapr refuses to open."""


def validate_url(url: str) -> str:
    """Return ``url`` when it uses an allowed scheme, otherwise raise."""
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ALLOWED_SCHEMES:
        raise InsecureURLError(
            f"Refusing to open URL with scheme {parsed.scheme or '<empty>'!r}; "
            f"allowed schemes: {', '.join(sorted(ALLOWED_SCHEMES))}"
        )
    if not parsed.netloc:
        raise InsecureURLError(f"URL is missing a host: {url!r}")
    return url


def request_json(
    url: str,
    *,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 30.0,
) -> Any:
    """Perform a JSON HTTP request and return the decoded body.

    Raises the usual :mod:`urllib` errors on failure; callers decide how to
    degrade (the gateway falls back to the deterministic offline engine).
    """
    validate_url(url)
    request_headers = {"Accept": "application/json", **(headers or {})}
    data: bytes | None = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        request_headers.setdefault("Content-Type", "application/json")

    request = urllib.request.Request(url, data=data, headers=request_headers, method=method)
    # validate_url() restricts schemes to HTTP(S); Bandit cannot infer this check.
    with urllib.request.urlopen(request, timeout=timeout) as response:  # nosec B310
        body = response.read().decode("utf-8", errors="replace")
    return json.loads(body) if body.strip() else {}
