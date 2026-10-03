"""Public Click CLI entry point and legacy command exports."""

from typing import Any

from synapr.cli import commands as _commands  # noqa: F401 - registers command groups
from synapr.cli.app import _orchestrator, _service, main  # noqa: F401 - compatibility exports

__all__ = ["_orchestrator", "_service", "main"]

_COMMAND_MODULES = tuple(
    getattr(_commands, name)
    for name in ("core", "config", "research", "github", "mail", "dashboard")
)


def __getattr__(name: str) -> Any:
    """Expose command callbacks formerly declared directly in this module."""
    for module in _COMMAND_MODULES:
        if hasattr(module, name):
            return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


if __name__ == "__main__":
    main()
