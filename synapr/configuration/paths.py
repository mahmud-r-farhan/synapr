"""Configuration file discovery and default path helpers."""

from __future__ import annotations

from pathlib import Path

from .constants import CONFIG_FILENAMES


def default_config_path(base_dir: str | Path | None = None) -> Path:
    """Return the canonical configuration file location for a project directory."""
    return Path(base_dir or ".").resolve() / CONFIG_FILENAMES[0]

def discover_config_file(
    config_path: str | Path | None = None,
    base_dir: str | Path | None = None,
) -> Path | None:
    """Locate the configuration file Synapr would load, or ``None`` when absent."""
    root = Path(base_dir or ".")
    candidates: list[Path] = []
    if config_path:
        candidates.append(Path(config_path))
    candidates.extend(root / name for name in CONFIG_FILENAMES)
    candidates.append(Path.home() / ".synapr" / "config.json")
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None
