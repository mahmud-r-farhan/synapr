"""Public configuration API, implemented by the modular configuration package."""

from synapr.configuration.constants import (
    CONFIG_FILENAMES,
    ENV_PREFIX,
    SECRET_MASK,
    SUPPORTED_PROVIDERS,
)
from synapr.configuration.env_file import load_env_file, parse_env_text, write_env_file
from synapr.configuration.env_registry import ENV_SPECS_BY_PATH, ENV_VAR_SPECS
from synapr.configuration.env_types import EnvVarSpec
from synapr.configuration.metadata import ConfigMeta
from synapr.configuration.model import SynaprConfig
from synapr.configuration.models import (
    BrowserConfig,
    EditorConfig,
    EmailConfig,
    GatewayConfig,
    GitHubConfig,
    PerceptionConfig,
    PipelineConfig,
    UIConfig,
    WorktreeConfig,
)
from synapr.configuration.paths import default_config_path, discover_config_file
from synapr.configuration.reporting import env_var_report, render_env_example
from synapr.configuration.values import (
    coerce_env_value,
    deep_merge,
    field_widget,
    get_by_path,
    redact_secret,
    set_by_path,
)

__all__ = [
    "CONFIG_FILENAMES", "ENV_PREFIX", "ENV_SPECS_BY_PATH", "ENV_VAR_SPECS", "SECRET_MASK",
    "SUPPORTED_PROVIDERS", "BrowserConfig", "ConfigMeta", "EditorConfig", "EmailConfig",
    "EnvVarSpec", "GatewayConfig", "GitHubConfig", "PerceptionConfig", "PipelineConfig",
    "SynaprConfig", "UIConfig", "WorktreeConfig", "coerce_env_value", "deep_merge",
    "default_config_path", "discover_config_file", "env_var_report", "field_widget",
    "get_by_path", "load_env_file", "parse_env_text", "redact_secret", "render_env_example",
    "set_by_path", "write_env_file",
]
