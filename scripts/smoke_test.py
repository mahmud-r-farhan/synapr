#!/usr/bin/env python
"""End-to-end smoke test for a *installed* Synapr distribution.

Runs the real CLI and boots the real dashboard in a subprocess, then exercises
the public HTTP surface (status, configuration, environment, provider probe).

Used by the ``smoke`` GitHub workflow on Linux, macOS and Windows; it is fully
cross-platform and never touches the network beyond localhost.

Usage:
    python scripts/smoke_test.py [--port 8799]
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

TIMEOUT = 90.0

# Windows consoles default to a legacy code page; force UTF-8 so the status
# glyphs below (and rich output from the child CLI) never raise UnicodeEncodeError.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    except (AttributeError, ValueError):  # pragma: no cover - exotic stream
        pass

# Environment forced onto every child process for the same reason.
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


def smoke_cli(workspace: Path) -> None:
    step("CLI: version, init, scan, status")
    check("synapr" in run_cli(["--version"], workspace), "`synapr --version` works")
    check("Created" in run_cli(["init"], workspace), "`synapr init` writes synapr.config.json")
    check((workspace / "synapr.config.json").is_file(), "configuration file exists")
    check((workspace / ".env.example").is_file(), ".env.example generated")
    check("Discovered" in run_cli(["scan"], workspace), "`synapr scan` works")
    check("Synapr Swarm Status" in run_cli(["status"], workspace), "`synapr status` works")

    step("CLI: configuration management")
    run_cli(["config", "set", "gateway.default_provider", "ollama"], workspace)
    check(
        json.loads(run_cli(["config", "get", "gateway.default_provider"], workspace)) == "ollama",
        "`synapr config set/get` round-trips",
    )
    run_cli(["config", "unset", "gateway.default_provider"], workspace)
    check(
        json.loads(run_cli(["config", "get", "gateway.default_provider"], workspace)) == "mock",
        "`synapr config unset` restores the default",
    )
    run_cli(["config", "set", "gateway.temperature", "9"], workspace, expect_success=False)
    ok("invalid values are rejected")
    check("valid" in run_cli(["config", "validate"], workspace), "`synapr config validate` passes")
    check("SYNAPR_PROVIDER" in run_cli(["config", "env", "--all"], workspace), "env registry listed")
    check("mock" in run_cli(["config", "test"], workspace), "`synapr config test` probes the provider")

    step("CLI: planning and dry-run swarm")
    check("Plan Verified" in run_cli(["plan", "Add a metrics endpoint"], workspace), "`synapr plan` works")
    check(
        "Swarm Execution Complete" in run_cli(["run", "Add a metrics endpoint", "--dry-run"], workspace),
        "`synapr run --dry-run` completes",
    )


def smoke_dashboard(workspace: Path, port: int) -> None:
    base_url = f"http://127.0.0.1:{port}"
    step(f"Dashboard: booting `synapr ui` on {base_url}")
    process = subprocess.Popen(
        [sys.executable, "-m", "synapr", "ui", "--port", str(port), "--no-open-browser"],
        cwd=str(workspace),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=CHILD_ENV,
    )
    try:
        wait_for_server(base_url, process)
        ok("dashboard is healthy")

        status, page = http("GET", f"{base_url}/")
        check(status == 200 and "Synapr" in str(page), "dashboard HTML served")
        check(http("GET", f"{base_url}/assets/app.js")[0] == 200, "static assets served")

        status, payload = http("GET", f"{base_url}/api/status")
        check(status == 200 and payload["status"] == "online", "/api/status online")

        status, payload = http("GET", f"{base_url}/api/config")
        check(status == 200 and "gateway" in payload["config"], "/api/config returns configuration")

        status, payload = http("GET", f"{base_url}/api/config/schema")
        check(status == 200 and len(payload["sections"]) >= 6, "/api/config/schema describes the form")

        status, payload = http(
            "PUT",
            f"{base_url}/api/config",
            {"config": {"gateway": {"planner_model": "smoke:latest"}}, "persist": True},
        )
        check(
            status == 200 and payload["config"]["gateway"]["planner_model"] == "smoke:latest",
            "visual configuration update applied",
        )
        on_disk = json.loads((workspace / "synapr.config.json").read_text(encoding="utf-8"))
        check(on_disk["gateway"]["planner_model"] == "smoke:latest", "update persisted to disk")

        status, payload = http(
            "PUT", f"{base_url}/api/config", {"config": {"ui": {"port": 123456}}}
        )
        check(status == 400, "invalid configuration is rejected with HTTP 400")

        status, payload = http(
            "PUT",
            f"{base_url}/api/config",
            {"config": {"gateway": {"openai_api_key": "sk-smoke-secret-0001"}}, "persist": False},
        )
        check(status == 200, "secret accepted")
        _, snapshot = http("GET", f"{base_url}/api/config")
        check(
            "sk-smoke-secret-0001" not in json.dumps(snapshot),
            "secrets are never returned in clear text",
        )

        status, payload = http(
            "POST",
            f"{base_url}/api/config/env",
            {"values": {"SYNAPR_PROVIDER": "lmstudio"}, "persist": True},
        )
        check(
            status == 200 and payload["config"]["gateway"]["default_provider"] == "lmstudio",
            "environment variable declared visually",
        )
        check("SYNAPR_PROVIDER=lmstudio" in (workspace / ".env").read_text(encoding="utf-8"),
              ".env file written")

        status, payload = http("POST", f"{base_url}/api/config/test-provider", {"provider": "mock"})
        check(status == 200 and payload["ok"] is True, "provider probe works")

        status, payload = http("POST", f"{base_url}/api/execute", {"goal": "Smoke", "dry_run": True})
        check(status == 200, "swarm execution can be queued")
    finally:
        process.terminate()
        try:
            process.wait(timeout=20)
        except subprocess.TimeoutExpired:  # pragma: no cover - defensive
            process.kill()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8799)
    args = parser.parse_args()

    # ``ignore_cleanup_errors`` keeps Windows happy: git objects inside the
    # provisioned worktrees are read-only and resist shutil.rmtree.
    with tempfile.TemporaryDirectory(prefix="synapr-smoke-", ignore_cleanup_errors=True) as tmp:
        workspace = Path(tmp)
        subprocess.run(["git", "init"], cwd=str(workspace), check=True, capture_output=True)
        try:
            smoke_cli(workspace)
            smoke_dashboard(workspace, free_port(args.port))
        except SmokeFailure as failure:
            print(f"\n\033[91m[FAIL] Smoke test failed: {failure}\033[0m", flush=True)
            return 1
        finally:
            # Detach git worktrees before the directory is removed.
            subprocess.run(
                ["git", "worktree", "prune"], cwd=str(workspace), capture_output=True, check=False
            )
    print("\n\033[92m[OK] All smoke checks passed\033[0m", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
