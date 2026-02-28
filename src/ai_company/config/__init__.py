"""YAML configuration loading and validation.

Public API
----------
.. autosummary::
    load_config
    load_config_from_string
    default_config_dict
    RootConfig
    AgentConfig
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
from ai_company.config.loader import load_config, load_config_from_string
from ai_company.config.schema import (
    AgentConfig,
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
    "ProviderConfig",
    "ProviderModelConfig",
    "RootConfig",
    "RoutingConfig",
    "RoutingRuleConfig",
    "default_config_dict",
    "load_config",
    "load_config_from_string",
]
