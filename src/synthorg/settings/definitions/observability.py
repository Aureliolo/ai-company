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
            "json_format (bool), rotation (object with strategy, "
            "max_bytes, backup_count, compress_rotated "
            "(builtin-only; rejected with external strategy))"
        ),
        group="Sinks",
        level=SettingLevel.ADVANCED,
        yaml_path="logging.sink_overrides",
    )
)

_r.register(
    SettingDefinition(
        namespace=SettingNamespace.OBSERVABILITY,
        key="custom_sinks",
        type=SettingType.JSON,
        default="[]",
        description=(
            "Additional sinks as JSON array. Each entry may specify "
            "sink_type (file, syslog, http; default file). "
            "File: file_path (required), level, json_format, rotation, "
            "routing_prefixes. "
            "Syslog: syslog_host (required), syslog_port, "
            "syslog_facility, syslog_protocol, level. "
            "HTTP: http_url (required), http_headers, http_batch_size, "
            "http_flush_interval_seconds, http_timeout_seconds, "
            "http_max_retries, level"
        ),
        group="Sinks",
        level=SettingLevel.ADVANCED,
        yaml_path="logging.custom_sinks",
    )
)
