#!/usr/bin/env python
"""End-to-end smoke test for an installed Synapr distribution."""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.smoke_cli import smoke_cli  # noqa: E402
from scripts.smoke_common import (  # noqa: E402
    CHILD_ENV,
    TIMEOUT,
    SmokeFailure,
    check,
    free_port,
    http,
    ok,
    run_cli,
    step,
    wait_for_server,
)
from scripts.smoke_dashboard import smoke_dashboard  # noqa: E402

__all__ = [
    "CHILD_ENV",
    "TIMEOUT",
    "SmokeFailure",
    "check",
    "free_port",
    "http",
    "main",
    "ok",
    "run_cli",
    "smoke_cli",
    "smoke_dashboard",
    "step",
    "wait_for_server",
]


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
