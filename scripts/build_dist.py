#!/usr/bin/env python
"""Cross-platform packaging script for Synapr.

Compiles standalone binaries using PyInstaller and packages them into
installer-style distributions for each target platform:
  - Windows: Inno Setup Wizard installer (.exe) + standalone .zip
  - Linux: Debian package (.deb) + standalone .tar.gz
  - macOS: Application archive (.tar.gz)

Usage:
    python scripts/build_dist.py [--no-installer]
"""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
BUILD = ROOT / "build"
VERSION = "0.1.0"


# Windows consoles default to a legacy code page (e.g. cp1252); force UTF-8 with replacement
# so status glyphs or subprocess output never raise UnicodeEncodeError.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    except (AttributeError, ValueError):
        pass

# Force UTF-8 in child processes (PyInstaller, dpkg, ISCC, git)
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


def package_linux(app_dir: Path, build_deb: bool = True) -> list[Path]:
    """Package Linux tar.gz and Debian package (.deb)."""
    artifacts: list[Path] = []
    arch = "amd64" if platform.machine() in ("x86_64", "AMD64") else "arm64"

    # 1. Standalone tar.gz
    tar_path = DIST / f"synapr-linux-{platform.machine()}-v{VERSION}.tar.gz"
    log(f"Creating Linux tarball: {tar_path.name}")
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

    # 2. Debian .deb package
    if build_deb and shutil.which("dpkg-deb"):
        log("Constructing Debian package tree...")
        deb_root = BUILD / "deb_pkg"
        if deb_root.exists():
            shutil.rmtree(deb_root)

        bin_dir = deb_root / "usr" / "lib" / "synapr"
        bin_dir.mkdir(parents=True, exist_ok=True)
        shutil.copytree(app_dir, bin_dir, dirs_exist_ok=True)

        # /usr/bin/synapr symlink / wrapper
        symlink_dir = deb_root / "usr" / "bin"
        symlink_dir.mkdir(parents=True, exist_ok=True)
        wrapper = symlink_dir / "synapr"
        wrapper.write_text(
            "#!/bin/sh\nexec /usr/lib/synapr/synapr \"$@\"\n", encoding="utf-8"
        )
        wrapper.chmod(0o755)

        # Desktop entry & Icon
        apps_dir = deb_root / "usr" / "share" / "applications"
        icons_dir = deb_root / "usr" / "share" / "icons" / "hicolor" / "scalable" / "apps"
        apps_dir.mkdir(parents=True, exist_ok=True)
        icons_dir.mkdir(parents=True, exist_ok=True)

        ico_src = ROOT / "synapr" / "assets" / "image.ico"
        if ico_src.is_file():
            shutil.copy2(ico_src, icons_dir / "synapr.ico")

        desktop_entry = (
            "[Desktop Entry]\n"
            "Name=Synapr Swarm OS\n"
            "Comment=Autonomous Local Multi-IDE AI Development Orchestrator (Zero Data Leak)\n"
            "Exec=/usr/bin/synapr ui --open-browser\n"
            "Icon=/usr/share/icons/hicolor/scalable/apps/synapr.ico\n"
            "Terminal=false\n"
            "Type=Application\n"
            "Categories=Development;IDE;\n"
        )
        (apps_dir / "synapr.desktop").write_text(desktop_entry, encoding="utf-8")

        # Debian control file
        debian_dir = deb_root / "DEBIAN"
        debian_dir.mkdir(parents=True, exist_ok=True)
        control_content = (
            f"Package: synapr\n"
            f"Version: {VERSION}\n"
            f"Section: devel\n"
            f"Priority: optional\n"
            f"Architecture: {arch}\n"
            f"Maintainer: Synapr Maintainers <maintainers@synapr.local>\n"
            f"Description: Autonomous local multi-IDE AI development orchestrator\n"
            f" 100% Local Air-Gapped Swarm OS with zero data leak or telemetry collection.\n"
        )
        (debian_dir / "control").write_text(control_content, encoding="utf-8")

        deb_output = DIST / f"synapr_{VERSION}_{arch}.deb"
        subprocess.check_call(["dpkg-deb", "--build", str(deb_root), str(deb_output)], env=ENV)
        ok(f"Created Debian package: {deb_output.name} ({deb_output.stat().st_size:,} bytes)")
        artifacts.append(deb_output)

    return artifacts


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
