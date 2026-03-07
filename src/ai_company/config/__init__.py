"""YAML configuration loading and validation.

Public API
----------
.. autosummary::
    load_config
    load_config_from_string
    discover_config
    bootstrap_logging
    default_config_dict
    RootConfig
    AgentConfig
    GracefulShutdownConfig
    ProviderConfig
    ProviderModelConfig
    RoutingConfig
    RoutingRuleConfig
    ConfigError
    ConfigFileNotFoundError
    ConfigParseError
    ConfigValidationError
    ConfigLocation
"""

from ai_company.config.defaults import default_config_dict
from ai_company.config.errors import (
    ConfigError,
    ConfigFileNotFoundError,
    ConfigLocation,
    ConfigParseError,
    ConfigValidationError,
)
from ai_company.config.loader import (
    bootstrap_logging,
    discover_config,
    load_config,
    load_config_from_string,
)
from ai_company.config.schema import (
    AgentConfig,
    GracefulShutdownConfig,
    ProviderConfig,
    ProviderModelConfig,
    RootConfig,
    RoutingConfig,
    RoutingRuleConfig,
)

__all__ = [
    "AgentConfig",
    "ConfigError",
    "ConfigFileNotFoundError",
    "ConfigLocation",
    "ConfigParseError",
    "ConfigValidationError",
    "GracefulShutdownConfig",
    "ProviderConfig",
    "ProviderModelConfig",
    "RootConfig",
    "RoutingConfig",
    "RoutingRuleConfig",
    "bootstrap_logging",
    "default_config_dict",
    "discover_config",
    "load_config",
    "load_config_from_string",
]
