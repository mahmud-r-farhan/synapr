"""Ordered environment variable registry shared by all configuration clients."""

from .env_specs_core import SPECS as CORE_SPECS
from .env_specs_integrations import SPECS as INTEGRATION_SPECS
from .env_specs_runtime import SPECS as RUNTIME_SPECS
from .env_types import EnvVarSpec

ENV_VAR_SPECS: tuple[EnvVarSpec, ...] = (*CORE_SPECS, *RUNTIME_SPECS, *INTEGRATION_SPECS)
ENV_SPECS_BY_PATH: dict[str, EnvVarSpec] = {spec.path: spec for spec in ENV_VAR_SPECS}
