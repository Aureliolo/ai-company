"""Observability namespace setting definitions."""

from synthorg.settings.enums import SettingLevel, SettingNamespace, SettingType
from synthorg.settings.models import SettingDefinition
from synthorg.settings.registry import get_registry

_r = get_registry()

_r.register(
    SettingDefinition(
        namespace=SettingNamespace.OBSERVABILITY,
        key="root_log_level",
        type=SettingType.ENUM,
        default="debug",
        description="Root logger level",
        group="Logging",
        enum_values=("debug", "info", "warning", "error", "critical"),
        yaml_path="logging.root_level",
    )
)

_r.register(
    SettingDefinition(
        namespace=SettingNamespace.OBSERVABILITY,
        key="enable_correlation",
        type=SettingType.BOOLEAN,
        default="true",
        description="Enable correlation ID tracking across agent calls",
        group="Logging",
        level=SettingLevel.ADVANCED,
        yaml_path="logging.enable_correlation",
    )
)
