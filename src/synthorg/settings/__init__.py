"""Settings persistence layer -- DB-backed runtime configuration.

Provides a resolution chain (DB > env > YAML > code defaults) so
settings can be edited at runtime via the REST API without restarts.
"""

from synthorg.settings.enums import (
    SettingLevel,
    SettingNamespace,
    SettingSource,
    SettingType,
)
from synthorg.settings.errors import (
    SettingNotFoundError,
    SettingsEncryptionError,
    SettingsError,
    SettingValidationError,
)
from synthorg.settings.models import SettingDefinition, SettingEntry, SettingValue
from synthorg.settings.registry import SettingsRegistry, get_registry
from synthorg.settings.resolver import ConfigResolver
from synthorg.settings.subscriber import SettingsSubscriber

__all__ = [
    "ConfigResolver",
    "SettingDefinition",
    "SettingEntry",
    "SettingLevel",
    "SettingNamespace",
    "SettingNotFoundError",
    "SettingSource",
    "SettingType",
    "SettingValidationError",
    "SettingValue",
    "SettingsEncryptionError",
    "SettingsError",
    "SettingsRegistry",
    "SettingsSubscriber",
    "get_registry",
]
