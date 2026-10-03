"""Shared process, HTTP, and assertion helpers for the end-to-end smoke suite."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

TIMEOUT = 90.0

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    except (AttributeError, ValueError):  # pragma: no cover - exotic stream
        pass

CHILD_ENV = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1", "PYTHONUNBUFFERED": "1"}


class SmokeFailure(RuntimeError):
    """Raised when a smoke assertion fails."""


def step(message: str) -> None:
    print(f"\n\033[95m> {message}\033[0m", flush=True)


def ok(message: str) -> None:
    print(f"  \033[92m+ [OK]\033[0m {message}", flush=True)


def check(condition: bool, message: str) -> None:
    if not condition:
        raise SmokeFailure(message)
    ok(message)


def run_cli(args: list[str], cwd: Path, expect_success: bool = True) -> str:
    """Run the installed `synapr` CLI through the current interpreter."""
    completed = subprocess.run(
        [sys.executable, "-m", "synapr", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=CHILD_ENV,
    )
    output = completed.stdout + completed.stderr
    if expect_success and completed.returncode != 0:
        raise SmokeFailure(f"`synapr {' '.join(args)}` failed ({completed.returncode}):\n{output}")
    if not expect_success and completed.returncode == 0:
        raise SmokeFailure(f"`synapr {' '.join(args)}` unexpectedly succeeded:\n{output}")
    return output


def http(method: str, url: str, payload: dict | None = None) -> tuple[int, Any]:
    data = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method=method
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            body = response.read().decode("utf-8")
            return response.status, json.loads(body) if body.strip().startswith(("{", "[")) else body
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8")
        return exc.code, json.loads(body) if body.strip().startswith(("{", "[")) else body


def free_port(preferred: int) -> int:
    with socket.socket() as probe:
        try:
            probe.bind(("127.0.0.1", preferred))
            return preferred
        except OSError:
            probe.bind(("127.0.0.1", 0))
            return int(probe.getsockname()[1])


def wait_for_server(base_url: str, process: subprocess.Popen) -> None:
    deadline = time.time() + TIMEOUT
    while time.time() < deadline:
        if process.poll() is not None:
            raise SmokeFailure(f"Dashboard exited early with code {process.returncode}")
        try:
            status, payload = http("GET", f"{base_url}/api/health")
            if status == 200 and isinstance(payload, dict) and payload.get("status") == "ok":
                return
        except Exception:
            time.sleep(0.5)
    raise SmokeFailure("Dashboard did not become healthy in time")
