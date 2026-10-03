"""Regression tests for URL and local-host validation boundaries."""

from unittest.mock import patch

from synapr.browser.engine import validate_localhost
from synapr.browser.search import fetch_webpage, search_searxng


def test_browser_fetchers_reject_non_http_urls() -> None:
    """Block non-HTTP schemes before any urllib request reaches the network layer."""
    with patch("urllib.request.urlopen") as mock_open:
        page = fetch_webpage("file:///etc/passwd")
        results = search_searxng("test", searxng_url="file:///etc")

    assert page.status_code == 400
    assert page.error
    assert results == []
    mock_open.assert_not_called()


def test_validate_localhost_rejects_unsafe_schemes_and_hosts() -> None:
    """Only HTTP(S) loopback URLs may be probed as local development servers."""
    with patch("urllib.request.urlopen") as mock_open:
        bad_scheme = validate_localhost("file:///etc/passwd")
        wildcard_host = validate_localhost("http://0.0.0.0:3000")

    assert not bad_scheme.reachable
    assert bad_scheme.has_errors
    assert not wildcard_host.reachable
    assert "non-local host" in wildcard_host.detail
    mock_open.assert_not_called()
