"""Environment variable introspection and example-file rendering."""

from __future__ import annotations

from typing import Any

from .env_registry import ENV_VAR_SPECS
from .model import SynaprConfig
from .values import get_by_path, redact_secret


def env_var_report(config: SynaprConfig | None = None) -> list[dict[str, Any]]:
    """Describe every supported environment variable and its current state."""
    cfg = config or SynaprConfig()
    report: list[dict[str, Any]] = []
    for spec in ENV_VAR_SPECS:
        hit = spec.read()
        try:
            current = get_by_path(cfg, spec.path)
        except KeyError:  # pragma: no cover - defensive
            current = None
        if spec.secret:
            current = redact_secret(current if isinstance(current, str) else None)
        report.append(
            {
                "name": spec.name,
                "aliases": list(spec.aliases),
                "path": spec.path,
                "kind": spec.kind,
                "secret": spec.secret,
                "description": spec.description,
                "example": spec.example,
                "is_set": hit is not None,
                "set_via": hit[0] if hit else None,
                "effective_value": current,
            }
        )
    return report

def render_env_example() -> str:
    """Render a ready-to-copy ``.env.example`` file documenting every variable."""
    lines = [
        "# ---------------------------------------------------------------------------",
        "# Synapr environment configuration",
        "#",
        "# Copy to `.env` (git-ignored) and uncomment what you need, or configure",
        "# everything visually with `synapr ui` -> Configuration tab.",
        "# Precedence: defaults < synapr.config.json < .env < real environment.",
        "# ---------------------------------------------------------------------------",
        "",
    ]
    current_section = ""
    for spec in ENV_VAR_SPECS:
        section = spec.path.split(".")[0] if "." in spec.path else "general"
        if section != current_section:
            current_section = section
            lines.append(f"# --- {section} " + "-" * max(0, 60 - len(section)))
        if spec.description:
            lines.append(f"# {spec.description}")
        if spec.aliases:
            lines.append(f"# Also accepts: {', '.join(spec.aliases)}")
        lines.append(f"# {spec.name}={spec.example}")
        lines.append("")
    return "\n".join(lines).rstrip("\n") + "\n"
