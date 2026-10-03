"""Tests for browser search, webpage fetching, dev-server verification, and CLI commands."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from synapr.browser.engine import validate_localhost
from synapr.browser.models import LocalhostValidationResult, SearchResult, WebPage
from synapr.browser.search import fetch_webpage, search_duckduckgo, search_searxng
from synapr.cli.main import main


def test_search_result_model() -> None:
    sr = SearchResult(title="Test Title", url="https://example.com", snippet="Test Snippet")
    assert sr.title == "Test Title"
    assert sr.url == "https://example.com"
    assert sr.snippet == "Test Snippet"


def test_webpage_model() -> None:
    wp = WebPage(url="https://example.com", title="Example", text="# Example\nHello world", status_code=200)
    assert wp.status_code == 200
    assert "Example" in wp.markdown
    assert "Example" in wp.text


def test_search_duckduckgo_parsing() -> None:
    fake_html = """
    <html><body>
    <div class="result">
        <h2 class="result__title"><a class="result__a result__url" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fpython.org&amp;rut=1">Python Programming</a></h2>
        <div class="result__snippet">Official Python website</div>
    </div>
    </body></html>
    """
    with patch("urllib.request.urlopen") as mock_open:
        mock_cm = MagicMock()
        mock_cm.read.return_value = fake_html.encode("utf-8")
        mock_cm.status = 200
        mock_cm.getcode.return_value = 200
        mock_cm.__enter__.return_value = mock_cm
        mock_open.return_value = mock_cm

        results = search_duckduckgo("python", max_results=5)
        assert len(results) >= 1
        assert "python.org" in results[0].url
        assert "Python" in results[0].title


def test_search_searxng_parsing() -> None:
    with patch("urllib.request.urlopen") as mock_open:
        mock_cm = MagicMock()
        mock_cm.read.return_value = b'{"results": [{"title": "FastAPI Docs", "url": "https://fastapi.tiangolo.com", "content": "Modern high performance web framework."}]}'
        mock_cm.status = 200
        mock_cm.getcode.return_value = 200
        mock_cm.__enter__.return_value = mock_cm
        mock_open.return_value = mock_cm

        results = search_searxng("fastapi", searxng_url="http://searxng.local:8080")
        assert len(results) == 1
        assert results[0].title == "FastAPI Docs"
        assert results[0].url == "https://fastapi.tiangolo.com"


def test_fetch_webpage_clean_markdown() -> None:
    html = """
    <!DOCTYPE html>
    <html>
    <head><title>My Documentation</title><style>body { color: red; }</style></head>
    <body>
        <script>console.log("secret");</script>
        <header><nav>Home | Docs</nav></header>
        <main>
            <h1>Introduction</h1>
            <p>Welcome to Synapr browser engine.</p>
            <pre><code>def run(): pass</code></pre>
        </main>
        <footer>Copyright 2026</footer>
    </body>
    </html>
    """
    with patch("urllib.request.urlopen") as mock_open:
        mock_cm = MagicMock()
        mock_cm.read.return_value = html.encode("utf-8")
        mock_cm.status = 200
        mock_cm.getcode.return_value = 200
        mock_cm.__enter__.return_value = mock_cm
        mock_open.return_value = mock_cm

        page = fetch_webpage("https://docs.example.com", max_chars=5000)
        assert page.title == "My Documentation"
        assert "Introduction" in page.text
        assert "Introduction" in page.markdown
        assert "Welcome to Synapr" in page.text
        assert "console.log" not in page.text


def test_validate_localhost_healthy() -> None:
    html = "<html><head><title>Vite + React</title></head><body><div id='root'>Ready</div></body></html>"
    with patch("urllib.request.urlopen") as mock_open:
        mock_cm = MagicMock()
        mock_cm.read.return_value = html.encode("utf-8")
        mock_cm.status = 200
        mock_cm.getcode.return_value = 200
        mock_cm.headers = MagicMock()
        mock_cm.headers.items.return_value = []
        mock_cm.__enter__.return_value = mock_cm
        mock_open.return_value = mock_cm

        res = validate_localhost("http://localhost:3000")
        assert res.reachable is True
        assert res.is_healthy is True
        assert res.status_code == 200
        assert res.title == "Vite + React"
        assert len(res.errors_detected) == 0


def test_validate_localhost_with_crash_banner() -> None:
    html = """
    <html><head><title>Server Error</title></head><body>
    <h1>Internal Server Error</h1>
    <pre>Traceback (most recent call last):
      File 'app.py', line 12, in index
    ZeroDivisionError: division by zero
    </pre>
    </body></html>
    """
    with patch("urllib.request.urlopen") as mock_open:
        mock_cm = MagicMock()
        mock_cm.read.return_value = html.encode("utf-8")
        mock_cm.status = 500
        mock_cm.getcode.return_value = 500
        mock_cm.headers = MagicMock()
        mock_cm.headers.items.return_value = []
        mock_cm.__enter__.return_value = mock_cm
        mock_open.return_value = mock_cm

        res = validate_localhost("http://localhost:8000")
        assert res.is_healthy is False
        assert res.has_errors is True
        assert res.status_code == 500
        assert any("Traceback" in err for err in res.errors_detected)


def test_cli_search_command() -> None:
    runner = CliRunner()
    fake_results = [
        SearchResult(title="Pytest Guide", url="https://docs.pytest.org", snippet="Full test runner documentation.")
    ]
    with patch("synapr.browser.search.search_web", return_value=fake_results):
        result = runner.invoke(main, ["search", "pytest", "--limit", "3"])
        assert result.exit_code == 0
        assert "Pytest Guide" in result.output
        assert "https://docs.pytest.org" in result.output


def test_cli_search_json() -> None:
    runner = CliRunner()
    fake_results = [
        SearchResult(title="Rust Docs", url="https://doc.rust-lang.org", snippet="The Rust Programming Language.")
    ]
    with patch("synapr.browser.search.search_web", return_value=fake_results):
        result = runner.invoke(main, ["search", "rust", "--json"])
        assert result.exit_code == 0
        assert "Rust Docs" in result.output
        assert '"url": "https://doc.rust-lang.org"' in result.output


def test_cli_fetch_command() -> None:
    runner = CliRunner()
    page = WebPage(url="http://example.com", title="Test Page", text="# Hello Markdown", status_code=200)
    with patch("synapr.browser.search.fetch_webpage", return_value=page):
        result = runner.invoke(main, ["fetch", "http://example.com"])
        assert result.exit_code == 0
        assert "Test Page" in result.output
        assert "# Hello Markdown" in result.output


def test_cli_test_url_command() -> None:
    runner = CliRunner()
    diag = LocalhostValidationResult(
        url="http://localhost:3000",
        reachable=True,
        status_code=200,
        latency_ms=12.5,
        title="App Title",
        has_errors=False,
        error_snippets=[],
    )
    with patch("synapr.browser.engine.validate_localhost", return_value=diag):
        result = runner.invoke(main, ["test-url", "http://localhost:3000"])
        assert result.exit_code == 0
        assert "Dev-Server Check" in result.output
        assert "Clean runtime" in result.output
