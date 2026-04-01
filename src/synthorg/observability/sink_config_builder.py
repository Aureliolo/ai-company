# ruff: noqa: TRY004 -- all type-validation paths deliberately raise ValueError
# for a consistent public API contract (callers use `except ValueError`).
"""Build a LogConfig from DEFAULT_SINKS + runtime overrides + custom sinks.

Pure-function module that merges static defaults with runtime settings
to produce a validated :class:`LogConfig` suitable for
:func:`configure_logging`.

The two JSON inputs come from ``SettingsService`` settings:

- ``sink_overrides``: JSON object keyed by sink identifier
  (``__console__`` for the console sink, file path for file sinks).
  Each value is an object with optional fields: ``enabled``, ``level``,
  ``json_format``, ``rotation``.
- ``custom_sinks``: JSON array of objects, each describing a new sink
  (file, syslog, or http).  File sinks require ``file_path``; syslog
  sinks require ``syslog_host``; HTTP sinks require ``http_url``.
  All types accept optional ``level``.
"""

import json
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Final, cast

from synthorg.observability import get_logger
from synthorg.observability.config import (
    DEFAULT_SINKS,
    LogConfig,
    RotationConfig,
    SinkConfig,
)
from synthorg.observability.enums import (
    LogLevel,
    RotationStrategy,
    SinkType,
    SyslogFacility,
    SyslogProtocol,
)

logger = get_logger(__name__)

CONSOLE_SINK_ID: Final[str] = "__console__"

# Set of file paths belonging to DEFAULT_SINKS (reserved, even if disabled).
DEFAULT_FILE_PATHS: frozenset[str] = frozenset(
    s.file_path for s in DEFAULT_SINKS if s.file_path is not None
)

# Valid sink identifiers for overrides.
_VALID_OVERRIDE_KEYS: frozenset[str] = DEFAULT_FILE_PATHS | {CONSOLE_SINK_ID}

_LEVEL_MAP: dict[str, LogLevel] = {level.value.lower(): level for level in LogLevel}

_STRATEGY_MAP: dict[str, RotationStrategy] = {
    s.value.lower(): s for s in RotationStrategy
}

# Allowed field names for strict validation.
_OVERRIDE_FIELDS: frozenset[str] = frozenset(
    {"enabled", "level", "json_format", "rotation"},
)
_CUSTOM_FILE_SINK_FIELDS: frozenset[str] = frozenset(
    {"sink_type", "file_path", "level", "json_format", "rotation", "routing_prefixes"},
)
_CUSTOM_SYSLOG_SINK_FIELDS: frozenset[str] = frozenset(
    {
        "sink_type",
        "syslog_host",
        "syslog_port",
        "syslog_facility",
        "syslog_protocol",
        "level",
    },
)
_CUSTOM_HTTP_SINK_FIELDS: frozenset[str] = frozenset(
    {
        "sink_type",
        "http_url",
        "http_headers",
        "http_batch_size",
        "http_flush_interval_seconds",
        "http_timeout_seconds",
        "http_max_retries",
        "level",
    },
)
# Union for initial parsing (field validation deferred to type-specific check)
_CUSTOM_SINK_FIELDS: frozenset[str] = (
    _CUSTOM_FILE_SINK_FIELDS | _CUSTOM_SYSLOG_SINK_FIELDS | _CUSTOM_HTTP_SINK_FIELDS
)
_ROTATION_FIELDS: frozenset[str] = frozenset(
    {"strategy", "max_bytes", "backup_count", "compress_rotated"},
)
_VALID_CUSTOM_SINK_TYPES: frozenset[str] = frozenset(
    {"file", "syslog", "http"},
)
_SYSLOG_FACILITY_MAP: dict[str, SyslogFacility] = {f.value: f for f in SyslogFacility}
_SYSLOG_PROTOCOL_MAP: dict[str, SyslogProtocol] = {p.value: p for p in SyslogProtocol}

_MAX_CUSTOM_SINKS: Final[int] = 20
_MAX_ROUTING_PREFIXES: Final[int] = 50


@dataclass(frozen=True, slots=True)
class SinkBuildResult:
    """Result of building a LogConfig from settings.

    Attributes:
        config: The fully validated logging configuration.
        routing_overrides: Custom sink routing entries keyed by
            file_path, mapping to logger name prefix tuples.
    """

    config: LogConfig
    routing_overrides: MappingProxyType[str, tuple[str, ...]]


# -- Validation helpers --------------------------------------------


def _reject_unknown_fields(
    fields: dict[str, Any],
    allowed: frozenset[str],
    context: str,
) -> None:
    """Raise ValueError if *fields* contains keys not in *allowed*."""
    unknown = set(fields) - allowed
    if unknown:
        msg = f"Unknown fields in {context}: {sorted(unknown)}"
        raise ValueError(msg)


def _parse_bool(raw: Any, *, field_name: str) -> bool:
    """Require an actual JSON boolean.

    Raises:
        ValueError: If *raw* is not a ``bool``.
    """
    if not isinstance(raw, bool):
        msg = f"{field_name} must be a boolean, got {type(raw).__name__}"
        raise ValueError(msg)
    return raw


# -- JSON parsing helpers ------------------------------------------


def _parse_json(raw: str, label: str) -> Any:
    """Parse a JSON string, raising ValueError on failure."""
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        msg = f"Invalid JSON for {label}: {exc}"
        raise ValueError(msg) from exc


def _parse_sink_overrides(raw: str) -> dict[str, dict[str, Any]]:
    """Parse and validate the ``sink_overrides`` JSON string.

    Returns:
        A dict mapping sink identifiers to override dicts.

    Raises:
        ValueError: On invalid JSON, wrong structure, unknown sink
            identifiers, or unknown override fields.
    """
    data = _parse_json(raw, "sink_overrides")
    if not isinstance(data, dict):
        msg = "sink_overrides must be a JSON object"
        raise ValueError(msg)

    for key, value in data.items():
        if key not in _VALID_OVERRIDE_KEYS:
            msg = (
                f"Unknown sink identifier in sink_overrides: {key!r}. "
                f"Valid keys: {sorted(_VALID_OVERRIDE_KEYS)}"
            )
            raise ValueError(msg)
        if not isinstance(value, dict):
            msg = (
                f"Override value for {key!r} must be a JSON object, "
                f"got {type(value).__name__}"
            )
            raise ValueError(msg)
        _reject_unknown_fields(
            value,
            _OVERRIDE_FIELDS,
            f"sink_overrides[{key!r}]",
        )
    return data


def _parse_custom_sinks(raw: str) -> list[dict[str, Any]]:
    """Parse and validate the ``custom_sinks`` JSON string.

    Returns:
        A list of custom sink definition dicts.

    Raises:
        ValueError: On invalid JSON, wrong structure, too many entries,
            or unknown fields.
    """
    data = _parse_json(raw, "custom_sinks")
    if not isinstance(data, list):
        msg = "custom_sinks must be a JSON array"
        raise ValueError(msg)

    if len(data) > _MAX_CUSTOM_SINKS:
        msg = f"custom_sinks exceeds maximum of {_MAX_CUSTOM_SINKS} entries"
        raise ValueError(msg)

    for i, entry in enumerate(data):
        if not isinstance(entry, dict):
            msg = f"custom_sinks[{i}] must be a JSON object, got {type(entry).__name__}"
            raise ValueError(msg)
        # Field validation is deferred to the type-specific builder
        # in _build_custom_sink, which calls _reject_unknown_fields
        # with the correct field set for the sink type.
    return data


# -- Level / rotation helpers --------------------------------------


def _parse_level(raw: Any) -> LogLevel:
    """Convert a level value to LogLevel (case-insensitive).

    Raises:
        ValueError: If *raw* is not a string or not a recognized level.
    """
    if not isinstance(raw, str):
        msg = f"level must be a string, got {type(raw).__name__}"
        raise ValueError(msg)
    level = _LEVEL_MAP.get(raw.lower())
    if level is None:
        valid = ", ".join(sorted(_LEVEL_MAP))
        msg = f"Invalid level {raw!r}. Valid levels: {valid}"
        raise ValueError(msg)
    return level


def _parse_rotation_override(
    raw: Any,
    base: RotationConfig | None,
) -> RotationConfig:
    """Merge a rotation override dict into an existing RotationConfig.

    Only fields present in *raw* are overridden; others are preserved
    from *base* (or defaults if base is None).

    Raises:
        ValueError: If *raw* is not a dict, contains unknown fields,
            or field values are invalid.
    """
    if not isinstance(raw, dict):
        msg = f"rotation must be a JSON object, got {type(raw).__name__}"
        raise ValueError(msg)
    _reject_unknown_fields(raw, _ROTATION_FIELDS, "rotation")

    base = base or RotationConfig()
    updates: dict[str, Any] = {}

    if "strategy" in raw:
        strategy = _STRATEGY_MAP.get(str(raw["strategy"]).lower())
        if strategy is None:
            valid = ", ".join(sorted(_STRATEGY_MAP))
            msg = f"Invalid rotation strategy {raw['strategy']!r}. Valid: {valid}"
            raise ValueError(msg)
        updates["strategy"] = strategy

    if "max_bytes" in raw:
        val = raw["max_bytes"]
        if not isinstance(val, int) or isinstance(val, bool):
            msg = f"Invalid max_bytes value {val!r}: must be an integer"
            raise ValueError(msg)
        updates["max_bytes"] = val

    if "backup_count" in raw:
        val = raw["backup_count"]
        if not isinstance(val, int) or isinstance(val, bool):
            msg = f"Invalid backup_count value {val!r}: must be an integer"
            raise ValueError(msg)
        updates["backup_count"] = val

    if "compress_rotated" in raw:
        updates["compress_rotated"] = _parse_bool(
            raw["compress_rotated"],
            field_name="rotation.compress_rotated",
        )

    if not updates:
        return base
    merged = {**base.model_dump(), **updates}
    return RotationConfig.model_validate(merged)


# -- Override application ------------------------------------------


def _apply_override(
    sink: SinkConfig,
    override: dict[str, Any],
    identifier: str,
) -> SinkConfig | None:
    """Apply an override dict to a single SinkConfig.

    Returns:
        The updated SinkConfig, or ``None`` if the sink is disabled.

    Raises:
        ValueError: If the console sink is disabled, types are wrong,
            or fields are invalid.
    """
    if "enabled" in override:
        enabled = _parse_bool(
            override["enabled"],
            field_name=f"sink_overrides[{identifier!r}].enabled",
        )
        if not enabled:
            if identifier == CONSOLE_SINK_ID:
                msg = (
                    "Cannot disable the console sink -- at least one output must remain"
                )
                raise ValueError(msg)
            return None

    updates: dict[str, Any] = {}

    if "level" in override:
        updates["level"] = _parse_level(override["level"])

    if "json_format" in override:
        updates["json_format"] = _parse_bool(
            override["json_format"],
            field_name=f"sink_overrides[{identifier!r}].json_format",
        )

    if "rotation" in override:
        updates["rotation"] = _parse_rotation_override(
            override["rotation"],
            sink.rotation,
        )

    if not updates:
        return sink
    merged = {**sink.model_dump(), **updates}
    return SinkConfig.model_validate(merged)


# -- Custom sink construction --------------------------------------


def _build_custom_sink(
    entry: dict[str, Any],
    index: int,
) -> SinkConfig:
    """Construct a SinkConfig from a custom sink definition dict.

    Dispatches to type-specific builders based on ``sink_type`` field.
    Defaults to ``"file"`` when ``sink_type`` is omitted.

    Raises:
        ValueError: If required fields are missing or invalid.
    """
    raw_type = entry.get("sink_type", "file")
    if not isinstance(raw_type, str):
        msg = f"custom_sinks[{index}].sink_type must be a string"
        raise ValueError(msg)
    sink_type_str = raw_type.lower()
    if sink_type_str not in _VALID_CUSTOM_SINK_TYPES:
        valid = ", ".join(sorted(_VALID_CUSTOM_SINK_TYPES))
        msg = (
            f"custom_sinks[{index}].sink_type {raw_type!r} is invalid. "
            f"Valid types: {valid}"
        )
        raise ValueError(msg)

    match sink_type_str:
        case "file":
            _reject_unknown_fields(
                entry,
                _CUSTOM_FILE_SINK_FIELDS,
                f"custom_sinks[{index}]",
            )
            return _build_custom_file_sink(entry, index)
        case "syslog":
            _reject_unknown_fields(
                entry,
                _CUSTOM_SYSLOG_SINK_FIELDS,
                f"custom_sinks[{index}]",
            )
            return _build_custom_syslog_sink(entry, index)
        case "http":
            _reject_unknown_fields(
                entry,
                _CUSTOM_HTTP_SINK_FIELDS,
                f"custom_sinks[{index}]",
            )
            return _build_custom_http_sink(entry, index)
        case _:  # pragma: no cover
            msg = f"Unhandled sink_type: {sink_type_str}"
            raise ValueError(msg)


def _build_custom_file_sink(
    entry: dict[str, Any],
    index: int,
) -> SinkConfig:
    """Build a FILE SinkConfig from a custom sink entry."""
    if "file_path" not in entry:
        msg = f"custom_sinks[{index}] is missing required field 'file_path'"
        raise ValueError(msg)

    raw_path = entry["file_path"]
    if not isinstance(raw_path, str) or not raw_path.strip():
        msg = (
            f"custom_sinks[{index}].file_path must be a non-empty string, "
            f"got {raw_path!r}"
        )
        raise ValueError(msg)
    normalized_path = raw_path.strip()
    level = _parse_level(entry["level"]) if "level" in entry else LogLevel.INFO

    json_format = True
    if "json_format" in entry:
        json_format = _parse_bool(
            entry["json_format"],
            field_name=f"custom_sinks[{index}].json_format",
        )

    rotation: RotationConfig | None = None
    if "rotation" in entry:
        rotation = _parse_rotation_override(entry["rotation"], None)
    else:
        rotation = RotationConfig()

    # SinkConfig's own validator handles path safety (absolute, traversal).
    return SinkConfig(
        sink_type=SinkType.FILE,
        level=level,
        file_path=normalized_path,
        rotation=rotation,
        json_format=json_format,
    )


def _parse_enum_field(
    entry: dict[str, Any],
    key: str,
    mapping: dict[str, Any],
    label: str,
    context: str,
) -> Any:
    """Parse a string field as an enum via a lookup map."""
    raw = entry[key]
    if not isinstance(raw, str):
        msg = f"{context}.{key} must be a string"
        raise ValueError(msg)
    parsed = mapping.get(raw.lower())
    if parsed is None:
        valid = ", ".join(sorted(mapping))
        msg = f"Invalid {label} {raw!r}. Valid: {valid}"
        raise ValueError(msg)
    return parsed


def _parse_common_sink_fields(
    entry: dict[str, Any],
    index: int,
    *,
    sink_type: str = "file",
) -> tuple[LogLevel, bool]:
    """Extract level and json_format from a custom sink entry.

    Args:
        entry: The custom sink entry dict.
        index: Index within the custom_sinks array.
        sink_type: The sink type string (file, syslog, http).

    Returns:
        Tuple of (level, json_format).

    Raises:
        ValueError: If json_format is set for syslog/http sinks.
    """
    level = _parse_level(entry["level"]) if "level" in entry else LogLevel.INFO
    json_format = True
    if "json_format" in entry:
        if sink_type in ("syslog", "http"):
            msg = (
                f"json_format is not supported for "
                f"{sink_type} sinks (custom_sinks[{index}])"
            )
            raise ValueError(msg)
        json_format = _parse_bool(
            entry["json_format"],
            field_name=f"custom_sinks[{index}].json_format",
        )
    return level, json_format


def _parse_int_field(
    entry: dict[str, Any],
    key: str,
    context: str,
) -> int:
    """Parse a strict integer field (rejects booleans)."""
    val = entry[key]
    if not isinstance(val, int) or isinstance(val, bool):
        msg = f"{context}.{key} must be an integer"
        raise ValueError(msg)
    return val


def _parse_number_field(
    entry: dict[str, Any],
    key: str,
    context: str,
) -> float:
    """Parse a numeric field (int or float, rejects booleans)."""
    val = entry[key]
    if not isinstance(val, int | float) or isinstance(val, bool):
        msg = f"{context}.{key} must be a number"
        raise ValueError(msg)
    return float(val)


def _parse_syslog_optional_fields(
    entry: dict[str, Any],
    ctx: str,
) -> tuple[int, SyslogFacility, SyslogProtocol]:
    """Parse optional syslog fields from a custom sink entry."""
    port = (
        _parse_int_field(entry, "syslog_port", ctx) if "syslog_port" in entry else 514
    )
    facility = (
        _parse_enum_field(
            entry,
            "syslog_facility",
            _SYSLOG_FACILITY_MAP,
            "syslog facility",
            ctx,
        )
        if "syslog_facility" in entry
        else SyslogFacility.USER
    )
    protocol = (
        _parse_enum_field(
            entry,
            "syslog_protocol",
            _SYSLOG_PROTOCOL_MAP,
            "syslog protocol",
            ctx,
        )
        if "syslog_protocol" in entry
        else SyslogProtocol.UDP
    )
    return port, facility, protocol


def _build_custom_syslog_sink(
    entry: dict[str, Any],
    index: int,
) -> SinkConfig:
    """Build a SYSLOG SinkConfig from a custom sink entry."""
    ctx = f"custom_sinks[{index}]"
    if "syslog_host" not in entry:
        msg = f"{ctx} is missing required field 'syslog_host' for syslog sink"
        raise ValueError(msg)

    raw_host = entry["syslog_host"]
    if not isinstance(raw_host, str) or not raw_host.strip():
        msg = f"{ctx}.syslog_host must be a non-empty string"
        raise ValueError(msg)

    level, _json_format = _parse_common_sink_fields(
        entry,
        index,
        sink_type="syslog",
    )
    port, facility, protocol = _parse_syslog_optional_fields(
        entry,
        ctx,
    )

    return SinkConfig(
        sink_type=SinkType.SYSLOG,
        level=level,
        syslog_host=raw_host.strip(),
        syslog_port=port,
        syslog_facility=facility,
        syslog_protocol=protocol,
    )


_HEADER_PAIR_LEN = 2


def _parse_http_headers(
    entry: dict[str, Any],
    index: int,
) -> tuple[tuple[str, str], ...]:
    """Parse and validate HTTP headers from a custom sink entry."""
    raw_headers = entry["http_headers"]
    if not isinstance(raw_headers, list):
        msg = f"custom_sinks[{index}].http_headers must be an array"
        raise ValueError(msg)
    headers: list[tuple[str, str]] = []
    for j, pair in enumerate(raw_headers):
        if (
            not isinstance(pair, list)
            or len(pair) != _HEADER_PAIR_LEN
            or not isinstance(pair[0], str)
            or not isinstance(pair[1], str)
        ):
            msg = (
                f"custom_sinks[{index}].http_headers[{j}] must be "
                "a [name, value] string pair"
            )
            raise ValueError(msg)
        headers.append((pair[0], pair[1]))
    return tuple(headers)


def _build_custom_http_sink(
    entry: dict[str, Any],
    index: int,
) -> SinkConfig:
    """Build an HTTP SinkConfig from a custom sink entry."""
    ctx = f"custom_sinks[{index}]"
    if "http_url" not in entry:
        msg = f"{ctx} is missing required field 'http_url' for http sink"
        raise ValueError(msg)

    raw_url = entry["http_url"]
    if not isinstance(raw_url, str) or not raw_url.strip():
        msg = f"{ctx}.http_url must be a non-empty string"
        raise ValueError(msg)

    level, _json_format = _parse_common_sink_fields(
        entry,
        index,
        sink_type="http",
    )
    kwargs: dict[str, Any] = {
        "sink_type": SinkType.HTTP,
        "level": level,
        "http_url": raw_url.strip(),
    }

    for int_key in ("http_batch_size", "http_max_retries"):
        if int_key in entry:
            kwargs[int_key] = _parse_int_field(entry, int_key, ctx)

    for num_key in ("http_flush_interval_seconds", "http_timeout_seconds"):
        if num_key in entry:
            kwargs[num_key] = _parse_number_field(entry, num_key, ctx)

    if "http_headers" in entry:
        kwargs["http_headers"] = _parse_http_headers(entry, index)

    return SinkConfig(**kwargs)


def _extract_routing(
    entry: dict[str, Any],
    file_path: str,
) -> tuple[str, ...] | None:
    """Extract and validate routing prefixes from a custom sink entry.

    Returns:
        A tuple of prefix strings, or ``None`` if no routing specified.

    Raises:
        ValueError: If prefixes are invalid, not an array, or too many.
    """
    raw = entry.get("routing_prefixes")
    if raw is None:
        return None
    if not isinstance(raw, list):
        msg = f"routing_prefixes for {file_path!r} must be an array"
        raise ValueError(msg)

    if len(raw) > _MAX_ROUTING_PREFIXES:
        msg = (
            f"routing_prefixes for {file_path!r} exceeds "
            f"maximum of {_MAX_ROUTING_PREFIXES} entries"
        )
        raise ValueError(msg)

    prefixes: list[str] = []
    for i, prefix in enumerate(raw):
        if not isinstance(prefix, str) or not prefix.strip():
            msg = f"routing_prefixes[{i}] for {file_path!r} must be a non-empty string"
            raise ValueError(msg)
        prefixes.append(prefix.strip())

    return tuple(prefixes) if prefixes else None


# -- Main builder --------------------------------------------------


def _merge_default_sinks(
    overrides: dict[str, dict[str, Any]],
) -> list[SinkConfig]:
    """Apply overrides to DEFAULT_SINKS, returning the merged list."""
    merged: list[SinkConfig] = []
    for sink in DEFAULT_SINKS:
        identifier = cast(
            "str",
            CONSOLE_SINK_ID if sink.sink_type == SinkType.CONSOLE else sink.file_path,
        )
        override = overrides.get(identifier)
        if override is not None:
            result = _apply_override(sink, override, identifier)
            if result is not None:
                merged.append(result)
        else:
            merged.append(sink)
    return merged


def _process_custom_entries(
    custom_entries: list[dict[str, Any]],
    merged: list[SinkConfig],
) -> MappingProxyType[str, tuple[str, ...]]:
    """Build custom sinks, append to *merged*, return routing overrides."""
    used_paths = DEFAULT_FILE_PATHS  # reserved even if disabled
    custom_paths: set[str] = set()
    routing_overrides: dict[str, tuple[str, ...]] = {}

    for i, entry in enumerate(custom_entries):
        sink = _build_custom_sink(entry, i)

        # FILE sinks need path uniqueness and routing
        if sink.sink_type == SinkType.FILE:
            path = cast("str", sink.file_path)

            if path in used_paths:
                msg = (
                    f"custom_sinks[{i}] file_path {path!r} conflicts "
                    "with a default sink (reserved even if disabled)"
                )
                raise ValueError(msg)
            if path in custom_paths:
                msg = (
                    f"custom_sinks[{i}] file_path {path!r} is duplicated "
                    "within custom_sinks"
                )
                raise ValueError(msg)

            custom_paths.add(path)

            prefixes = _extract_routing(entry, path)
            if prefixes is not None:
                routing_overrides[path] = prefixes

        # SYSLOG/HTTP sinks are catch-all (no routing, no file_path)
        merged.append(sink)

    return MappingProxyType(routing_overrides)


def build_log_config_from_settings(
    *,
    root_level: LogLevel,
    enable_correlation: bool,
    sink_overrides_json: str,
    custom_sinks_json: str,
    log_dir: str = "logs",
) -> SinkBuildResult:
    """Merge DEFAULT_SINKS with runtime overrides and custom sinks.

    Args:
        root_level: Root logger level.
        enable_correlation: Whether to enable correlation ID tracking.
        sink_overrides_json: JSON object of per-sink overrides.
        custom_sinks_json: JSON array of custom sink definitions.
        log_dir: Directory for log files.

    Returns:
        A :class:`SinkBuildResult` containing the validated
        :class:`LogConfig` and any routing overrides for custom sinks.

    Raises:
        ValueError: On invalid JSON, validation failures, or
            attempts to disable the console sink.
    """
    overrides = _parse_sink_overrides(sink_overrides_json)
    custom_entries = _parse_custom_sinks(custom_sinks_json)

    merged = _merge_default_sinks(overrides)
    routing = _process_custom_entries(custom_entries, merged)

    config = LogConfig(
        root_level=root_level,
        enable_correlation=enable_correlation,
        sinks=tuple(merged),
        log_dir=log_dir,
    )
    return SinkBuildResult(config=config, routing_overrides=routing)
