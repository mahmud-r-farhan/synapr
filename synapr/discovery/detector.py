"""Cross-platform discovery of installed IDEs and AI development tools."""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
from pathlib import Path

from synapr.core.logger import logger
from synapr.core.models import EditorInfo, EditorType
from synapr.discovery.catalog import KNOWN_EDITORS


class EditorDetector:
    """Discover code editors available on the host system."""

    KNOWN_EDITORS = KNOWN_EDITORS

    def __init__(self, custom_overrides: dict[str, str] | None = None) -> None:
        self.custom_overrides = custom_overrides or {}
        self.os_name = platform.system().lower()

    def discover_all(self) -> list[EditorInfo]:
        """Scan the host system and return all discovered editors."""
        discovered: list[EditorInfo] = []

        for candidate in self.KNOWN_EDITORS:
            info = self._check_candidate(candidate)
            if info:
                discovered.append(info)

        # Check custom overrides configured by user
        for custom_id, custom_path in self.custom_overrides.items():
            if custom_path and (shutil.which(custom_path) or Path(custom_path).is_file()):
                resolved = shutil.which(custom_path) or str(Path(custom_path).resolve())
                discovered.append(
                    EditorInfo(
                        id=custom_id,
                        name=f"Custom ({custom_id})",
                        editor_type=EditorType.CUSTOM,
                        executable_path=resolved,
                        is_available=True,
                        launch_args_template=["{path}"],
                    )
                )

        logger.info(f"Discovered {len(discovered)} installed code editors on {platform.system()}")
        return discovered

    def find_editor(self, editor_id: str) -> EditorInfo | None:
        """Find a specific editor by identifier."""
        # 1. Check custom overrides
        if editor_id in self.custom_overrides:
            path = self.custom_overrides[editor_id]
            resolved = shutil.which(path) or (str(Path(path).resolve()) if Path(path).is_file() else None)
            if resolved:
                return EditorInfo(
                    id=editor_id,
                    name=f"Custom ({editor_id})",
                    editor_type=EditorType.CUSTOM,
                    executable_path=resolved,
                    is_available=True,
                )

        # 2. Check known candidates
        for candidate in self.KNOWN_EDITORS:
            if candidate["id"] == editor_id:
                return self._check_candidate(candidate)

        # 3. Fallback: try resolving command directly in PATH
        resolved = shutil.which(editor_id)
        if resolved:
            return EditorInfo(
                id=editor_id,
                name=editor_id.title(),
                editor_type=EditorType.CUSTOM,
                executable_path=resolved,
                is_available=True,
            )

        return None

    def _check_candidate(self, candidate: dict) -> EditorInfo | None:
        """Check if an editor candidate exists via PATH or standard directories."""
        # 1. Check PATH
        for exe in candidate["executables"]:
            found = shutil.which(exe)
            if found:
                version = self._get_version(found, candidate.get("version_flag"))
                return EditorInfo(
                    id=candidate["id"],
                    name=candidate["name"],
                    editor_type=candidate["type"],
                    executable_path=found,
                    version=version,
                    launch_args_template=candidate.get("launch_template", ["{path}"]),
                    is_available=True,
                )

        # 2. Check OS-specific standard directories
        paths_to_check: list[str] = []
        if self.os_name == "windows":
            paths_to_check = candidate.get("windows_paths", [])
        elif self.os_name == "darwin":
            paths_to_check = candidate.get("mac_paths", [])
        else:
            paths_to_check = candidate.get("linux_paths", [])

        for p_str in paths_to_check:
            expanded = os.path.expandvars(p_str)
            # Handle glob patterns if needed (e.g. IntelliJ*)
            if "*" in expanded:
                import glob
                matches = glob.glob(expanded)
                if matches and Path(matches[0]).is_file():
                    target_path = matches[0]
                    version = self._get_version(target_path, candidate.get("version_flag"))
                    return EditorInfo(
                        id=candidate["id"],
                        name=candidate["name"],
                        editor_type=candidate["type"],
                        executable_path=target_path,
                        version=version,
                        launch_args_template=candidate.get("launch_template", ["{path}"]),
                        is_available=True,
                    )
            elif Path(expanded).is_file():
                version = self._get_version(expanded, candidate.get("version_flag"))
                return EditorInfo(
                    id=candidate["id"],
                    name=candidate["name"],
                    editor_type=candidate["type"],
                    executable_path=expanded,
                    version=version,
                    launch_args_template=candidate.get("launch_template", ["{path}"]),
                    is_available=True,
                )

        return None

    def _get_version(self, executable: str, flag: str | None) -> str | None:
        """Attempt to extract version string from executable without blocking."""
        if not flag:
            return None
        try:
            res = subprocess.run(
                [executable, flag],
                capture_output=True,
                text=True,
                timeout=2.0,
                creationflags=(
                    subprocess.CREATE_NO_WINDOW  # type: ignore[attr-defined]  # Windows-only flag
                    if platform.system() == "Windows"
                    else 0
                ),
            )
            if res.returncode == 0 and res.stdout.strip():
                lines = res.stdout.strip().splitlines()
                return lines[0].strip()
        except Exception:
            pass
        return None
