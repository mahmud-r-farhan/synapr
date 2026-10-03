"""PyInstaller invocation for Synapr distribution builds."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from scripts.dist_common import DIST, ENV, ROOT, log, ok


def run_pyinstaller() -> Path:
    """Run PyInstaller using packaging/synapr.spec."""
    log("Running PyInstaller build...")
    spec_path = ROOT / "packaging" / "synapr.spec"
    if not spec_path.is_file():
        raise FileNotFoundError(f"Spec file not found at {spec_path}")

    cmd = [sys.executable, "-m", "PyInstaller", str(spec_path), "--noconfirm"]
    subprocess.check_call(cmd, cwd=str(ROOT), env=ENV)
    app_dir = DIST / "synapr"
    if not app_dir.is_dir():
        raise RuntimeError(f"Expected PyInstaller output directory at {app_dir}")
    ok(f"PyInstaller build complete: {app_dir}")
    return app_dir
