"""Linux archive and Debian package creation."""

from __future__ import annotations

import platform
import shutil
import subprocess
import tarfile
from pathlib import Path

from scripts.dist_common import BUILD, DIST, ENV, ROOT, VERSION, log, ok


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
