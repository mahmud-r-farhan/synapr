"""Unit tests for the hardened HTTP helper used by every outbound request."""

import json
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from synapr.core.http import InsecureURLError, request_json, validate_url


class _Handler(BaseHTTPRequestHandler):
    """Tiny echo server used to exercise request_json without the network."""

    def _respond(self, payload: dict) -> None:
        body = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 - http.server API
        self._respond({"method": "GET", "path": self.path, "auth": self.headers.get("Authorization")})

    def do_POST(self) -> None:  # noqa: N802 - http.server API
        length = int(self.headers.get("Content-Length", 0))
        payload = json.loads(self.rfile.read(length) or b"{}")
        self._respond({"method": "POST", "echo": payload})

    def log_message(self, *args: object) -> None:  # pragma: no cover - silence test output
        return


@pytest.fixture
def server() -> Iterator[str]:
    httpd = HTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{httpd.server_address[1]}"
    finally:
        httpd.shutdown()
        httpd.server_close()


@pytest.mark.parametrize("url", ["file:///etc/passwd", "ftp://example.com/x", "gopher://x", "/local"])
def test_validate_url_rejects_dangerous_schemes(url: str) -> None:
    with pytest.raises(InsecureURLError):
        validate_url(url)


def test_validate_url_requires_host() -> None:
    with pytest.raises(InsecureURLError):
        validate_url("http://")


def test_validate_url_accepts_http_and_https() -> None:
    assert validate_url("http://localhost:11434/api/tags")
    assert validate_url("https://api.openai.com/v1/models")


def test_request_json_get_with_headers(server: str) -> None:
    payload = request_json(f"{server}/models", headers={"Authorization": "Bearer token"})

    assert payload["method"] == "GET"
    assert payload["path"] == "/models"
    assert payload["auth"] == "Bearer token"


def test_request_json_post_sends_payload(server: str) -> None:
    payload = request_json(f"{server}/chat", method="POST", payload={"model": "x"})

    assert payload["method"] == "POST"
    assert payload["echo"] == {"model": "x"}


def test_request_json_refuses_file_scheme(tmp_path) -> None:
    secret = tmp_path / "secret.json"
    secret.write_text('{"leak": true}', encoding="utf-8")

    with pytest.raises(InsecureURLError):
        request_json(secret.as_uri())
