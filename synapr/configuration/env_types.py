"""Environment variable specification type."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class EnvVarSpec:
    """Declarative binding between an environment variable and a config field."""

    name: str
    path: str
    kind: Literal["str", "int", "float", "bool", "csv", "json"] = "str"
    secret: bool = False
    aliases: tuple[str, ...] = ()
    description: str = ""
    example: str = ""

    @property
    def names(self) -> tuple[str, ...]:
        """All accepted variable names, canonical first."""
        return (self.name, *self.aliases)

    def read(self, environ: dict[str, str] | None = None) -> tuple[str, str] | None:
        """Return the first configured variable name and raw value."""
        env = environ if environ is not None else os.environ
        for name in self.names:
            raw = env.get(name)
            if raw is not None and raw != "":
                return name, raw
        return None
