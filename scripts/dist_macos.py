"""macOS archive packaging."""

from __future__ import annotations

import platform
import tarfile
from pathlib import Path

from scripts.dist_common import DIST, ROOT, VERSION, log, ok


def package_macos(app_dir: Path) -> list[Path]:
    """Package macOS tar.gz."""
    artifacts: list[Path] = []
    machine = platform.machine()
    tar_path = DIST / f"synapr-macos-{machine}-v{VERSION}.tar.gz"
    log(f"Creating macOS tarball: {tar_path.name}")
    with tarfile.open(tar_path, "w:gz") as tf:
        for file_path in app_dir.rglob("*"):
            if file_path.is_file():
                arcname = Path("synapr") / file_path.relative_to(app_dir)
                tf.add(file_path, arcname=str(arcname))
        for extra in ["LICENSE", "readme.md"]:
            if (ROOT / extra).is_file():
                tf.add(ROOT / extra, arcname=f"synapr/{extra}")
    ok(f"Created {tar_path.name} ({tar_path.stat().st_size:,} bytes)")
    artifacts.append(tar_path)
    return artifacts
