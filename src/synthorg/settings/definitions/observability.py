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

_r.register(
    SettingDefinition(
        namespace=SettingNamespace.OBSERVABILITY,
        key="sink_overrides",
        type=SettingType.JSON,
        default="{}",
        description=(
            "Per-sink overrides keyed by sink identifier "
            "(__console__ or file path). Each value is an object with "
            "optional fields: enabled (bool), level (string), "
            "json_format (bool), rotation (object with max_bytes, "
            "backup_count, strategy)"
        ),
        group="Sinks",
        level=SettingLevel.ADVANCED,
    )
)

_r.register(
    SettingDefinition(
        namespace=SettingNamespace.OBSERVABILITY,
        key="custom_sinks",
        type=SettingType.JSON,
        default="[]",
        description=(
            "Additional file sinks as JSON array. Each entry: "
            "file_path (required), level (string, default info), "
            "json_format (bool, default true), rotation (object), "
            "routing_prefixes (array of logger name prefix strings)"
        ),
        group="Sinks",
        level=SettingLevel.ADVANCED,
    )
)
