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
from typing import Any

from synthorg.observability.config import (
    DEFAULT_SINKS,
    LogConfig,
    RotationConfig,
    SinkConfig,
)
from synthorg.observability.enums import LogLevel, RotationStrategy, SinkType

_CONSOLE_ID = "__console__"

# Set of file paths belonging to DEFAULT_SINKS (reserved, even if disabled).
_DEFAULT_FILE_PATHS: frozenset[str] = frozenset(
    s.file_path for s in DEFAULT_SINKS if s.file_path is not None
)

# Valid sink identifiers for overrides.
_VALID_OVERRIDE_KEYS: frozenset[str] = _DEFAULT_FILE_PATHS | {_CONSOLE_ID}

_LEVEL_MAP: dict[str, LogLevel] = {level.value.lower(): level for level in LogLevel}

_STRATEGY_MAP: dict[str, RotationStrategy] = {
    s.value.lower(): s for s in RotationStrategy
}


@dataclass(frozen=True, slots=True)
class SinkBuildResult:
    """Result of building a LogConfig from settings.

    Attributes:
        config: The fully validated logging configuration.
        routing_overrides: Custom sink routing entries keyed by
            file_path, mapping to logger name prefix tuples.
    """

    config: LogConfig
    routing_overrides: dict[str, tuple[str, ...]]


# ── JSON parsing helpers ─────────────────────────────────────────


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
        ValueError: On invalid JSON, wrong structure, or unknown keys.
    """
    data = _parse_json(raw, "sink_overrides")
    if not isinstance(data, dict):
        msg = "sink_overrides must be a JSON object"
        raise TypeError(msg)

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
            raise TypeError(msg)
    return data


def _parse_custom_sinks(
    raw: str,
) -> list[dict[str, Any]]:
    """Parse and validate the ``custom_sinks`` JSON string.

    Returns:
        A list of custom sink definition dicts.

    Raises:
        ValueError: On invalid JSON or wrong structure.
    """
    data = _parse_json(raw, "custom_sinks")
    if not isinstance(data, list):
        msg = "custom_sinks must be a JSON array"
        raise TypeError(msg)

    for i, entry in enumerate(data):
        if not isinstance(entry, dict):
            msg = f"custom_sinks[{i}] must be a JSON object, got {type(entry).__name__}"
            raise TypeError(msg)
    return data


# ── Level / rotation helpers ─────────────────────────────────────


def _parse_level(raw: str) -> LogLevel:
    """Convert a lowercase level string to LogLevel.

    Raises:
        ValueError: If the level string is not recognized.
    """
    level = _LEVEL_MAP.get(raw.lower())
    if level is None:
        valid = ", ".join(sorted(_LEVEL_MAP))
        msg = f"Invalid level {raw!r}. Valid levels: {valid}"
        raise ValueError(msg)
    return level


def _parse_rotation_override(
    raw: dict[str, Any],
    base: RotationConfig | None,
) -> RotationConfig:
    """Merge a rotation override dict into an existing RotationConfig.

    Only fields present in *raw* are overridden; others are preserved
    from *base* (or defaults if base is None).

    Raises:
        ValueError: If strategy string is unrecognized.
    """
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
        updates["max_bytes"] = int(raw["max_bytes"])

    if "backup_count" in raw:
        updates["backup_count"] = int(raw["backup_count"])

    return base.model_copy(update=updates) if updates else base


# ── Override application ─────────────────────────────────────────


def _apply_override(
    sink: SinkConfig,
    override: dict[str, Any],
    identifier: str,
) -> SinkConfig | None:
    """Apply an override dict to a single SinkConfig.

    Returns:
        The updated SinkConfig, or ``None`` if the sink is disabled.

    Raises:
        ValueError: If the console sink is disabled or fields are invalid.
    """
    if "enabled" in override and not override["enabled"]:
        if identifier == _CONSOLE_ID:
            msg = "Cannot disable the console sink -- at least one output must remain"
            raise ValueError(msg)
        return None

    updates: dict[str, Any] = {}

    if "level" in override:
        updates["level"] = _parse_level(override["level"])

    if "json_format" in override:
        updates["json_format"] = bool(override["json_format"])

    if "rotation" in override:
        updates["rotation"] = _parse_rotation_override(
            override["rotation"],
            sink.rotation,
        )

    return sink.model_copy(update=updates) if updates else sink


# ── Custom sink construction ─────────────────────────────────────


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

    file_path = str(entry["file_path"])
    level = _parse_level(entry["level"]) if "level" in entry else LogLevel.INFO
    json_format = bool(entry.get("json_format", True))

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
        ValueError: If any prefix is empty or whitespace-only.
    """
    raw = entry.get("routing_prefixes")
    if raw is None:
        return None
    if not isinstance(raw, list):
        msg = f"routing_prefixes for {file_path!r} must be an array"
        raise TypeError(msg)

    prefixes: list[str] = []
    for i, prefix in enumerate(raw):
        s = str(prefix).strip()
        if not s:
            msg = (
                f"routing_prefixes[{i}] for {file_path!r} "
                "must be a non-empty prefix string"
            )
            raise ValueError(msg)
        prefixes.append(s)

    return tuple(prefixes) if prefixes else None


# ── Main builder ─────────────────────────────────────────────────


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

    # 1. Apply overrides to DEFAULT_SINKS.
    merged: list[SinkConfig] = []
    for sink in DEFAULT_SINKS:
        identifier: str = (
            _CONSOLE_ID if sink.sink_type == SinkType.CONSOLE else sink.file_path  # type: ignore[assignment]
        )

        override = overrides.get(identifier)
        if override is not None:
            result = _apply_override(sink, override, identifier)
            if result is not None:
                merged.append(result)
        else:
            merged.append(sink)

    # 2. Build custom sinks and collect routing.
    used_paths = _DEFAULT_FILE_PATHS  # reserved even if disabled
    custom_paths: set[str] = set()
    routing_overrides: dict[str, tuple[str, ...]] = {}

    for i, entry in enumerate(custom_entries):
        sink = _build_custom_sink(entry, i)
        path: str = sink.file_path  # type: ignore[assignment]

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

        # Extract routing prefixes (if any).
        prefixes = _extract_routing(entry, path)
        if prefixes is not None:
            routing_overrides[path] = prefixes

    # 3. Build and validate LogConfig.
    config = LogConfig(
        root_level=root_level,
        enable_correlation=enable_correlation,
        sinks=tuple(merged),
        log_dir=log_dir,
    )

    return SinkBuildResult(config=config, routing_overrides=routing_overrides)
