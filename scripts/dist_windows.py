"""Windows archive and Inno Setup packaging."""

from __future__ import annotations

import os
import shutil
import subprocess
import zipfile
from pathlib import Path

from scripts.dist_common import DIST, ENV, ROOT, VERSION, log, ok, warn


def package_windows(app_dir: Path, build_installer: bool = True) -> list[Path]:
    """Package Windows standalone zip and Inno Setup installer."""
    artifacts: list[Path] = []

    # 1. Standalone zip archive
    zip_path = DIST / f"synapr-windows-x64-v{VERSION}.zip"
    log(f"Creating Windows zip bundle: {zip_path.name}")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for file_path in app_dir.rglob("*"):
            if file_path.is_file():
                arcname = Path("synapr") / file_path.relative_to(app_dir)
                zf.write(file_path, arcname)
        # Include license, readme, privacy notice, icon
        for extra in ["LICENSE", "readme.md"]:
            if (ROOT / extra).is_file():
                zf.write(ROOT / extra, Path("synapr") / extra)
        if (ROOT / "synapr" / "assets" / "image.ico").is_file():
            zf.write(ROOT / "synapr" / "assets" / "image.ico", Path("synapr") / "image.ico")
    ok(f"Created {zip_path.name} ({zip_path.stat().st_size:,} bytes)")
    artifacts.append(zip_path)

    # 2. Inno Setup installer
    if build_installer:
        iss_path = ROOT / "packaging" / "windows" / "synapr.iss"
        iscc = shutil.which("iscc") or r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
        if os.path.exists(iscc) and iss_path.is_file():
            log(f"Compiling Inno Setup installer with {iscc}...")
            cmd = [iscc, str(iss_path)]
            subprocess.check_call(cmd, cwd=str(ROOT), env=ENV)
            installer_path = DIST / "Synapr-Setup-x64.exe"
            target_installer = DIST / f"Synapr-Setup-x64-v{VERSION}.exe"
            if installer_path.is_file():
                if target_installer != installer_path:
                    shutil.copy2(installer_path, target_installer)
                ok(f"Created Inno Setup installer: {target_installer.name} ({target_installer.stat().st_size:,} bytes)")
                artifacts.append(target_installer)
                if installer_path != target_installer:
                    artifacts.append(installer_path)
        else:
            warn(f"Inno Setup compiler (ISCC) not found at {iscc}. Skipping installer creation.")

    return artifacts
