"""Read, update, and secure local .env files."""

from __future__ import annotations

import os
import stat
from pathlib import Path


def parse_env_text(text: str) -> dict[str, str]:
    """Parse ``.env`` style content into a mapping (supports ``export`` and quotes)."""
    values: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.lower().startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if not key:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        values[key] = value
    return values

def load_env_file(path: str | Path = ".env", override: bool = False) -> dict[str, str]:
    """Load a ``.env`` file into :data:`os.environ` and return the parsed mapping."""
    env_path = Path(path)
    if not env_path.is_file():
        return {}
    try:
        values = parse_env_text(env_path.read_text(encoding="utf-8"))
    except OSError:
        return {}
    for key, value in values.items():
        if override or key not in os.environ:
            os.environ[key] = value
    return values

def write_env_file(
    values: dict[str, str],
    path: str | Path = ".env",
    remove: list[str] | None = None,
) -> Path:
    """Create or update a ``.env`` file, preserving unrelated lines and comments."""
    env_path = Path(path)
    removals = set(remove or [])
    lines: list[str] = []
    if env_path.is_file():
        lines = env_path.read_text(encoding="utf-8").splitlines()

    remaining = dict(values)
    output: list[str] = []
    for line in lines:
        stripped = line.strip()
        candidate = stripped[7:].strip() if stripped.lower().startswith("export ") else stripped
        key = candidate.partition("=")[0].strip() if "=" in candidate else ""
        if key and key in removals:
            continue
        if key and key in remaining:
            output.append(f"{key}={remaining.pop(key)}")
        else:
            output.append(line)

    if remaining:
        if output and output[-1].strip():
            output.append("")
        output.append("# Managed by Synapr")
        output.extend(f"{key}={value}" for key, value in remaining.items())

    env_path.parent.mkdir(parents=True, exist_ok=True)
    env_path.write_text("\n".join(output).rstrip("\n") + "\n", encoding="utf-8")
    _harden_permissions(env_path)
    return env_path

def _harden_permissions(path: Path) -> None:
    """Best-effort ``chmod 600`` so secrets are not world readable on POSIX hosts."""
    if os.name == "nt":
        return
    try:
        path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        # Permission hardening is best-effort on restricted or unusual filesystems.
        pass
