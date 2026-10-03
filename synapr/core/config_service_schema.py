"""Declarative configurator schema for every supported setting."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, get_args

from pydantic import BaseModel

from synapr.config import (
    ENV_SPECS_BY_PATH,
    SUPPORTED_PROVIDERS,
    SynaprConfig,
    field_widget,
    get_by_path,
    redact_secret,
)

SELECT_OPTIONS: dict[str, list[str]] = {
    "gateway.default_provider": list(SUPPORTED_PROVIDERS),
    "perception.ocr_engine": ["auto", "tesseract", "windows_media", "regex_terminal"],
}

SECTION_META: dict[str, dict[str, str]] = {
    "general": {
        "title": "Project",
        "icon": "🧭",
        "description": "Identity of the workspace Synapr is orchestrating.",
    },
    "gateway": {
        "title": "LLM Gateway",
        "icon": "🌐",
        "description": "Local engines and optional remote providers, plus per-role models.",
    },
    "worktree": {
        "title": "Git Worktrees",
        "icon": "🌿",
        "description": "Isolation strategy for parallel agents.",
    },
    "editor": {
        "title": "Editors & Dispatch",
        "icon": "🖥️",
        "description": "How detected IDEs are matched to subtasks and launched.",
    },
    "perception": {
        "title": "Perception",
        "icon": "👁️",
        "description": "Optical window inspection and terminal telemetry.",
    },
    "pipeline": {
        "title": "Test & Merge Pipeline",
        "icon": "🧪",
        "description": "Automated verification and self-healing integration.",
    },
    "ui": {
        "title": "Dashboard",
        "icon": "🎛️",
        "description": "Local control center behaviour and safety switches.",
    },
    "browser": {
        "title": "Web & Research",
        "icon": "🔍",
        "description": "Search engine and live web documentation research parameters.",
    },
    "email": {
        "title": "Email Gateway",
        "icon": "✉️",
        "description": "Mail monitoring, triage, and draft generation.",
    },
    "github": {
        "title": "GitHub Integration",
        "icon": "🐙",
        "description": "Repository issue tracking, worktree mapping, and PR automation.",
    },
}

def _constraints(field_info: Any) -> dict[str, Any]:
    """Extract numeric constraints (ge/gt/le/lt) from a pydantic FieldInfo."""
    out: dict[str, Any] = {}
    for item in getattr(field_info, "metadata", []) or []:
        for attr, key in (("ge", "min"), ("gt", "exclusive_min"), ("le", "max"), ("lt", "exclusive_max")):
            value = getattr(item, attr, None)
            if value is not None:
                out[key] = value
    return out

def _humanise(name: str) -> str:
    """Turn ``max_self_healing_attempts`` into ``Max Self Healing Attempts``."""
    replacements = {"Url": "URL", "Api": "API", "Ui": "UI", "Ocr": "OCR", "Llm": "LLM"}
    words = [word.capitalize() for word in name.split("_")]
    return " ".join(replacements.get(word, word) for word in words)


class ConfigServiceSchemaMixin:
    if TYPE_CHECKING:
        @property
        def config(self) -> SynaprConfig: ...

    def schema(self, editor_ids: list[str] | None = None) -> dict[str, Any]:
        """Return a declarative form description for the visual configurator."""
        cfg = self.config
        env_overrides = cfg.meta.env_overrides
        sections: list[dict[str, Any]] = []

        general_fields: list[dict[str, Any]] = []
        for name, field_info in SynaprConfig.model_fields.items():
            annotation = field_info.annotation
            if isinstance(annotation, type) and issubclass(annotation, BaseModel):
                continue
            general_fields.append(
                self._describe_field(cfg, name, name, field_info, env_overrides, editor_ids)
            )
        if general_fields:
            sections.append({"key": "general", **SECTION_META["general"], "fields": general_fields})

        for section_name, section_field in SynaprConfig.model_fields.items():
            annotation = section_field.annotation
            if not (isinstance(annotation, type) and issubclass(annotation, BaseModel)):
                continue
            fields = [
                self._describe_field(
                    cfg,
                    f"{section_name}.{field_name}",
                    field_name,
                    field_info,
                    env_overrides,
                    editor_ids,
                )
                for field_name, field_info in annotation.model_fields.items()
            ]
            meta = SECTION_META.get(section_name, {"title": _humanise(section_name), "icon": "⚙️"})
            sections.append({"key": section_name, **meta, "fields": fields})

        return {
            "sections": sections,
            "providers": list(SUPPORTED_PROVIDERS),
            "env_prefix": "SYNAPR_",
        }

    def _describe_field(
        self,
        cfg: SynaprConfig,
        path: str,
        name: str,
        field_info: Any,
        env_overrides: dict[str, str],
        editor_ids: list[str] | None,
    ) -> dict[str, Any]:
        spec = ENV_SPECS_BY_PATH.get(path)
        widget = field_widget(field_info.annotation)
        options: list[str] | None = None

        literal_args = [arg for arg in get_args(field_info.annotation) if isinstance(arg, str)]
        if widget == "select" and literal_args:
            options = literal_args
        if path in SELECT_OPTIONS:
            widget, options = "select", list(SELECT_OPTIONS[path])
        if path == "editor.preferred_editor" and editor_ids:
            widget, options = "select", ["", *editor_ids]
        if spec is not None and spec.secret:
            widget = "password"

        try:
            value = get_by_path(cfg, path)
        except KeyError:  # pragma: no cover - defensive
            value = None
        if spec is not None and spec.secret:
            value = redact_secret(value if isinstance(value, str) else None)

        descriptor: dict[str, Any] = {
            "path": path,
            "name": name,
            "label": _humanise(name),
            "widget": widget,
            "nullable": type(None) in get_args(field_info.annotation),
            "help": field_info.description or (spec.description if spec else ""),
            "value": value,
            "secret": bool(spec and spec.secret),
            "env": spec.name if spec else None,
            "env_aliases": list(spec.aliases) if spec else [],
            "env_locked": path in env_overrides,
            "env_locked_by": env_overrides.get(path),
            "placeholder": spec.example if spec else "",
        }
        if options is not None:
            descriptor["options"] = options
        descriptor.update(_constraints(field_info))
        return descriptor
