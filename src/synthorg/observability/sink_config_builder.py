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
- ``custom_sinks``: JSON array of objects, each describing a new FILE
  sink with ``file_path`` (required) and optional ``level``,
  ``json_format``, ``rotation``, ``routing_prefixes``.
"""

import json
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, cast

from synthorg.observability import get_logger
from synthorg.observability.config import (
    DEFAULT_SINKS,
    LogConfig,
    RotationConfig,
    SinkConfig,
)
from synthorg.observability.enums import LogLevel, RotationStrategy, SinkType

logger = get_logger(__name__)

CONSOLE_SINK_ID: str = "__console__"

# Set of file paths belonging to DEFAULT_SINKS (reserved, even if disabled).
_DEFAULT_FILE_PATHS: frozenset[str] = frozenset(
    s.file_path for s in DEFAULT_SINKS if s.file_path is not None
)

# Valid sink identifiers for overrides.
_VALID_OVERRIDE_KEYS: frozenset[str] = _DEFAULT_FILE_PATHS | {CONSOLE_SINK_ID}

_LEVEL_MAP: dict[str, LogLevel] = {level.value.lower(): level for level in LogLevel}

_STRATEGY_MAP: dict[str, RotationStrategy] = {
    s.value.lower(): s for s in RotationStrategy
}

# Allowed field names for strict validation.
_OVERRIDE_FIELDS: frozenset[str] = frozenset(
    {"enabled", "level", "json_format", "rotation"},
)
_CUSTOM_SINK_FIELDS: frozenset[str] = frozenset(
    {"file_path", "level", "json_format", "rotation", "routing_prefixes"},
)
_ROTATION_FIELDS: frozenset[str] = frozenset(
    {"strategy", "max_bytes", "backup_count"},
)

_MAX_CUSTOM_SINKS: int = 20
_MAX_ROUTING_PREFIXES: int = 50


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
        _reject_unknown_fields(
            entry,
            _CUSTOM_SINK_FIELDS,
            f"custom_sinks[{i}]",
        )
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

    return base.model_copy(update=updates) if updates else base


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

    return sink.model_copy(update=updates) if updates else sink


# -- Custom sink construction --------------------------------------


def _build_custom_sink(
    entry: dict[str, Any],
    index: int,
) -> SinkConfig:
    """Construct a SinkConfig from a custom sink definition dict.

    Raises:
        ValueError: If ``file_path`` is missing or fields are invalid.
    """
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
    file_path = raw_path
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
        file_path=file_path,
        rotation=rotation,
        json_format=json_format,
    )


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
    used_paths = _DEFAULT_FILE_PATHS  # reserved even if disabled
    custom_paths: set[str] = set()
    routing_overrides: dict[str, tuple[str, ...]] = {}

    for i, entry in enumerate(custom_entries):
        sink = _build_custom_sink(entry, i)
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
        merged.append(sink)

        prefixes = _extract_routing(entry, path)
        if prefixes is not None:
            routing_overrides[path] = prefixes

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
