#!/usr/bin/env python
"""Cross-platform packaging script for Synapr.

Compiles the application with PyInstaller and packages native archives or installers.
Usage: python scripts/build_dist.py [--no-installer]
"""

from __future__ import annotations

import argparse
import platform
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dist_build import run_pyinstaller  # noqa: E402
from scripts.dist_common import BUILD, DIST, ENV, VERSION, log, ok, warn  # noqa: E402
from scripts.dist_linux import package_linux  # noqa: E402
from scripts.dist_macos import package_macos  # noqa: E402
from scripts.dist_windows import package_windows  # noqa: E402

__all__ = [
    "BUILD",
    "DIST",
    "ENV",
    "ROOT",
    "VERSION",
    "log",
    "main",
    "ok",
    "package_linux",
    "package_macos",
    "package_windows",
    "run_pyinstaller",
    "warn",
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Package Synapr for distribution")
    parser.add_argument("--no-installer", action="store_true", help="Skip native installer creation")
    args = parser.parse_args()

    DIST.mkdir(parents=True, exist_ok=True)
    app_dir = run_pyinstaller()

    current_os = platform.system()
    created: list[Path] = []
    if current_os == "Windows":
        created = package_windows(app_dir, build_installer=not args.no_installer)
    elif current_os == "Linux":
        created = package_linux(app_dir, build_deb=not args.no_installer)
    elif current_os == "Darwin":
        created = package_macos(app_dir)
    else:
        warn(f"Unknown OS: {current_os}")

    log("\nDistribution artifacts ready in dist/:")
    for artifact in created:
        print(f"  * {artifact.name} ({artifact.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
