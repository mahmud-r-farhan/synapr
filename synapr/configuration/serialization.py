"""Safe updates and atomic serialization for the root configuration model."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Self

from .constants import SECRET_MASK
from .env_file import _harden_permissions
from .env_registry import ENV_VAR_SPECS
from .metadata import ConfigMeta
from .values import deep_merge, get_by_path, redact_secret


class ConfigSerializationMixin:
    def apply_updates(self, updates: dict[str, Any]) -> Self:
        """Return a new validated configuration with ``updates`` deep-merged in.

        Masked secret placeholders coming back from the UI are ignored so that
        displaying a redacted key never destroys the real one.
        """
        config: Any = self
        cleaned = _strip_masked_secrets(updates)
        merged = deep_merge(config.model_dump(mode="json"), cleaned)
        new_cfg = type(config).model_validate(merged)
        new_cfg.meta = ConfigMeta(
            source_path=config.meta.source_path,
            env_file=config.meta.env_file,
            env_overrides=dict(config.meta.env_overrides),
            pre_env_values=dict(config.meta.pre_env_values),
        )
        return new_cfg

    def to_dict(self, *, redact: bool = False) -> dict[str, Any]:
        """Serialise the configuration, optionally masking secret values."""
        config: Any = self
        data = config.model_dump(mode="json")
        if redact:
            for spec in ENV_VAR_SPECS:
                if not spec.secret:
                    continue
                try:
                    value = get_by_path(config, spec.path)
                except KeyError:  # pragma: no cover - defensive
                    continue
                _assign_dict_path(data, spec.path, redact_secret(value))
        return data

    def secret_status(self) -> dict[str, bool]:
        """Map each secret config path to whether a value is currently configured."""
        config: Any = self
        status: dict[str, bool] = {}
        for spec in ENV_VAR_SPECS:
            if spec.secret:
                try:
                    status[spec.path] = bool(get_by_path(config, spec.path))
                except KeyError:  # pragma: no cover - defensive
                    status[spec.path] = False
        return status

    def file_state(self) -> dict[str, Any]:
        """Serialisable state excluding values that were injected by the environment."""
        config: Any = self
        data = config.model_dump(mode="json")
        for path, previous in config.meta.pre_env_values.items():
            _assign_dict_path(data, path, previous)
        return data

    def save(
        self,
        output_path: str | Path = "synapr.config.json",
        *,
        include_env_sourced: bool = False,
    ) -> Path:
        """Persist configuration to a JSON file atomically.

        Values provided by environment variables are *not* baked into the file by
        default, keeping the environment authoritative (and keys out of git).
        """
        config: Any = self
        target = Path(output_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = config.model_dump(mode="json") if include_env_sourced else config.file_state()
        serialised = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"

        fd, tmp_name = tempfile.mkstemp(
            prefix=".synapr-config-", suffix=".tmp", dir=str(target.parent or ".")
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(serialised)
            os.replace(tmp_name, target)
        except BaseException:
            Path(tmp_name).unlink(missing_ok=True)
            raise

        # mkstemp() creates 0600 files; relax to a normal config mode unless the
        # payload actually contains a secret, in which case keep it owner-only.
        if _payload_has_secret(payload):
            _harden_permissions(target)
        elif os.name != "nt":
            try:
                target.chmod(0o644)
            except OSError:  # pragma: no cover - exotic filesystems
                pass
        config.meta.source_path = str(target.resolve())
        return target

def _payload_has_secret(payload: dict[str, Any]) -> bool:
    """Return True when a serialised payload still contains a secret value."""
    for spec in ENV_VAR_SPECS:
        if not spec.secret:
            continue
        node: Any = payload
        for part in spec.path.split("."):
            if not isinstance(node, dict):
                node = None
                break
            node = node.get(part)
        if node:
            return True
    return False

def _assign_dict_path(data: dict[str, Any], path: str, value: Any) -> None:
    """Assign ``value`` at a dotted path inside a plain dictionary."""
    parts = path.split(".")
    node = data
    for part in parts[:-1]:
        child = node.get(part)
        if not isinstance(child, dict):
            return
        node = child
    node[parts[-1]] = value

def _strip_masked_secrets(updates: dict[str, Any]) -> dict[str, Any]:
    """Drop secret fields whose value is the redacted placeholder."""
    cleaned = json.loads(json.dumps(updates))  # deep copy, JSON-safe by construction
    for spec in ENV_VAR_SPECS:
        if not spec.secret:
            continue
        parts = spec.path.split(".")
        node = cleaned
        for part in parts[:-1]:
            child = node.get(part) if isinstance(node, dict) else None
            if not isinstance(child, dict):
                node = None
                break
            node = child
        if not isinstance(node, dict):
            continue
        leaf = parts[-1]
        if leaf in node:
            value = node[leaf]
            if isinstance(value, str) and value.startswith(SECRET_MASK):
                node.pop(leaf)
    return cleaned
