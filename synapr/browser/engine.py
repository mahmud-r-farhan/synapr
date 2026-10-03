"""Local development server validator and browser execution bridge."""

from __future__ import annotations

import re
import time
import urllib.error
import urllib.parse
import urllib.request

from synapr.browser.models import LocalhostValidationResult
from synapr.core.http import validate_url

CRASH_INDICATORS: tuple[str, ...] = (
    "Traceback (most recent call last)",
    "Internal Server Error",
    "Unhandled Runtime Error",
    "SyntaxError:",
    "ReferenceError:",
    "TypeError:",
    "Uncaught Exception",
    "ModuleNotFoundError:",
    "Build Error",
    "Compilation failed",
    "Failed to compile",
    "Cannot find module",
    "Hydration failed",
)


def validate_localhost(
    url: str = "http://localhost:3000",
    timeout: float = 6.0,
) -> LocalhostValidationResult:
    """Probe a local dev server and report HTTP health and error diagnostics."""
    try:
        validate_url(url)
    except ValueError as exc:
        return LocalhostValidationResult(
            url=url,
            reachable=False,
            has_errors=True,
            detail=str(exc),
        )

    parsed = urllib.parse.urlparse(url)
    host = parsed.hostname or "localhost"

    # Ensure this is actually a loopback host for safety
    if host not in {"localhost", "127.0.0.1", "::1"}:
        return LocalhostValidationResult(
            url=url,
            reachable=False,
            detail=f"Refusing to validate non-local host: {host}",
        )

    headers = {
        "User-Agent": "Synapr-DevValidator/0.1.0",
        "Accept": "text/html,application/json,*/*",
    }

    start = time.perf_counter()
    try:
        req = urllib.request.Request(url, headers=headers)
        # validate_url() restricts this outbound request to HTTP(S).
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # nosec B310
            latency_ms = (time.perf_counter() - start) * 1000.0
            status_code = resp.getcode()
            body = resp.read().decode("utf-8", errors="replace")
            response_headers = dict(resp.headers.items())

        # Extract title
        title_match = re.search(r"<title>(.*?)</title>", body, re.IGNORECASE | re.DOTALL)
        title = title_match.group(1).strip() if title_match else None

        # Check for crash or error traces in HTML
        error_snippets: list[str] = []
        for indicator in CRASH_INDICATORS:
            if indicator.lower() in body.lower():
                idx = body.lower().find(indicator.lower())
                snippet = body[max(0, idx - 40) : min(len(body), idx + 160)].strip()
                error_snippets.append(f"Found '{indicator}': {snippet}")

        has_errors = bool(error_snippets) or (status_code >= 400)
        detail = (
            f"Dev server at {url} is healthy ({status_code} OK, {latency_ms:.1f}ms)"
            if not has_errors
            else f"Dev server returned {status_code} with {len(error_snippets)} error pattern(s)"
        )

        return LocalhostValidationResult(
            url=url,
            reachable=True,
            status_code=status_code,
            latency_ms=round(latency_ms, 2),
            title=title,
            has_errors=has_errors,
            error_snippets=error_snippets[:5],
            detail=detail,
            headers=dict(list(response_headers.items())[:10]),
        )
    except urllib.error.HTTPError as exc:
        latency_ms = (time.perf_counter() - start) * 1000.0
        return LocalhostValidationResult(
            url=url,
            reachable=True,
            status_code=exc.code,
            latency_ms=round(latency_ms, 2),
            has_errors=True,
            detail=f"HTTP Error {exc.code}: {exc.reason}",
            error_snippets=[f"Server responded with error status {exc.code}"],
        )
    except Exception as exc:
        latency_ms = (time.perf_counter() - start) * 1000.0
        return LocalhostValidationResult(
            url=url,
            reachable=False,
            latency_ms=round(latency_ms, 2),
            has_errors=True,
            detail=f"Connection failed: {exc}",
        )
