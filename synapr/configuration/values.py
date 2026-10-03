"""Small, reusable helpers for reading and validating config values."""

from __future__ import annotations

import json
from typing import Any, Literal, get_args, get_origin

from pydantic import BaseModel

from .constants import FALSY_VALUES, SECRET_MASK, TRUTHY_VALUES


def redact_secret(value: str | None) -> str | None:
    """Return a masked representation of a secret, keeping the last 4 characters."""
    if not value:
        return None
    if len(value) <= 4:
        return SECRET_MASK
    return f"{SECRET_MASK}{value[-4:]}"

def coerce_env_value(kind: str, raw: str) -> Any:
    """Convert a raw environment string into the type expected by the config field."""
    text = raw.strip()
    if kind == "bool":
        lowered = text.lower()
        if lowered in TRUTHY_VALUES:
            return True
        if lowered in FALSY_VALUES:
            return False
        raise ValueError(f"Expected a boolean value, received {raw!r}")
    if kind == "int":
        return int(text)
    if kind == "float":
        return float(text)
    if kind == "csv":
        return [item.strip() for item in text.split(",") if item.strip()]
    if kind == "json":
        parsed = json.loads(text)
        if not isinstance(parsed, dict):
            raise ValueError("Expected a JSON object")
        return parsed
    return text

def get_by_path(model: BaseModel, path: str) -> Any:
    """Read a nested attribute using a dotted path (``gateway.planner_model``)."""
    current: Any = model
    for part in path.split("."):
        if not isinstance(current, BaseModel) or part not in type(current).model_fields:
            raise KeyError(f"Unknown configuration path: {path}")
        current = getattr(current, part)
    return current

def set_by_path(model: BaseModel, path: str, value: Any) -> None:
    """Assign a nested attribute using a dotted path, validating the new value."""
    parts = path.split(".")
    current: Any = model
    for part in parts[:-1]:
        if not isinstance(current, BaseModel) or part not in type(current).model_fields:
            raise KeyError(f"Unknown configuration path: {path}")
        current = getattr(current, part)
    leaf = parts[-1]
    if not isinstance(current, BaseModel) or leaf not in type(current).model_fields:
        raise KeyError(f"Unknown configuration path: {path}")
    setattr(current, leaf, value)

def deep_merge(base: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge ``updates`` into a copy of ``base``."""
    merged = dict(base)
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged

def field_widget(annotation: Any) -> str:
    """Infer the widget type the dashboard should render for a field annotation."""
    origin = get_origin(annotation)
    if origin is not None:
        args = [arg for arg in get_args(annotation) if arg is not type(None)]
        if origin is list:
            return "list"
        if origin is dict:
            return "keyvalue"
        if origin is Literal:
            return "select"
        if args:
            return field_widget(args[0])
    if annotation is bool:
        return "boolean"
    if annotation in (int, float):
        return "number"
    return "text"
