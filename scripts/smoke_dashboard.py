"""HTTP dashboard smoke checks against a launched Synapr CLI process."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.smoke_common import CHILD_ENV, check, http, ok, step, wait_for_server


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
        check(
            status == 200 and "Synapr" in str(page) and "SYNAPR:swarm" not in str(page),
            "assembled dashboard HTML served",
        )
        for asset in ("app.js", "bootstrap.js", "styles-views.css", "swarm.html", "config.html"):
            check(http("GET", f"{base_url}/assets/{asset}")[0] == 200, f"dashboard asset {asset} served")

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
