"""CLI-focused end-to-end smoke checks."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.smoke_common import check, ok, run_cli, step


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
