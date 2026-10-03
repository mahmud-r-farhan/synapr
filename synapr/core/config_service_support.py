"""Shared errors and validation formatting for configuration services."""

from __future__ import annotations

from pydantic import ValidationError


class ConfigServiceError(Exception):
    """Raised when a configuration mutation cannot be applied."""


def _format_validation_error(exc: ValidationError) -> str:
    """Render a pydantic validation error as a compact, user-facing message."""
    parts = []
    for error in exc.errors():
        location = ".".join(str(item) for item in error.get("loc", ()))
        parts.append(f"{location or 'config'}: {error.get('msg', 'invalid value')}")
    return "; ".join(parts) or str(exc)
