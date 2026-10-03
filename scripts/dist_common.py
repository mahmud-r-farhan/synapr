"""Shared paths, subprocess environment, and console output for distribution builds."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
BUILD = ROOT / "build"
VERSION = "0.1.0"

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    except (AttributeError, ValueError):
        pass

ENV = {
    **os.environ,
    "PYTHONUTF8": "1",
    "PYTHONIOENCODING": "utf-8",
    "PYTHONUNBUFFERED": "1",
}


def log(msg: str) -> None:
    print(f"\033[94m> [BUILD]\033[0m {msg}", flush=True)


def ok(msg: str) -> None:
    print(f"  \033[92m+ [OK]\033[0m {msg}", flush=True)


def warn(msg: str) -> None:
    print(f"  \033[93m! [WARN]\033[0m {msg}", flush=True)
