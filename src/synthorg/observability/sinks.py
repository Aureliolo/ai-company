"""Log handler factory for building stdlib handlers from sink config.

Translates :class:`~synthorg.observability.config.SinkConfig` instances
into fully configured :class:`logging.Handler` objects with the
appropriate structlog :class:`~structlog.stdlib.ProcessorFormatter`.
"""

import logging
import logging.handlers
import sys
from types import MappingProxyType
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

import structlog
from structlog.stdlib import ProcessorFormatter

from synthorg.observability.config import RotationConfig, SinkConfig
from synthorg.observability.enums import RotationStrategy, SinkType

# ── Flushing file handlers ────────────────────────────────────────
# Standard RotatingFileHandler and WatchedFileHandler buffer writes,
# so log entries may never reach disk in a long-running server with
# infrequent events.  These subclasses flush after every emit.


class _FlushingRotatingFileHandler(logging.handlers.RotatingFileHandler):
    """RotatingFileHandler that flushes to disk after every emit."""

    def emit(self, record: logging.LogRecord) -> None:
        super().emit(record)
        try:
            self.flush()
        except Exception:  # mirrors StreamHandler.emit
            self.handleError(record)


class _FlushingWatchedFileHandler(logging.handlers.WatchedFileHandler):
    """WatchedFileHandler that flushes to disk after every emit."""

    def emit(self, record: logging.LogRecord) -> None:
        super().emit(record)
        try:
            self.flush()
        except Exception:  # mirrors StreamHandler.emit
            self.handleError(record)


# ── Logger name routing ───────────────────────────────────────────

# Maps sink file_path to the logger name prefixes that should be
# routed to that sink.  Sinks not listed here are catch-all sinks
# (no name filter attached).
_SINK_ROUTING: MappingProxyType[str, tuple[str, ...]] = MappingProxyType(
    {
        "audit.log": (
            "synthorg.security.",
            "synthorg.hr.",
            "synthorg.observability.",
        ),
        "cost_usage.log": ("synthorg.budget.", "synthorg.providers."),
        "agent_activity.log": (
            "synthorg.engine.",
            "synthorg.core.",
            "synthorg.communication.",
            "synthorg.tools.",
            "synthorg.memory.",
        ),
        "access.log": ("synthorg.api.",),
        "persistence.log": ("synthorg.persistence.",),
        "configuration.log": ("synthorg.settings.", "synthorg.config."),
        "backup.log": ("synthorg.backup.",),
    }
)


class _LoggerNameFilter(logging.Filter):
    """Filter log records by logger name prefixes.

    When *include_prefixes* is non-empty, only records whose
    ``record.name`` starts with one of the prefixes are accepted.
    When *exclude_prefixes* is non-empty, records matching any
    exclude prefix are rejected (checked before includes).

    Args:
        include_prefixes: Accept only these prefixes (empty = accept all).
        exclude_prefixes: Reject these prefixes (empty = reject none).
    """

    def __init__(
        self,
        *,
        include_prefixes: tuple[str, ...] = (),
        exclude_prefixes: tuple[str, ...] = (),
    ) -> None:
        super().__init__()
        for prefix in (*include_prefixes, *exclude_prefixes):
            if not prefix or not prefix.strip():
                msg = "Logger name prefixes must be non-empty strings"
                raise ValueError(msg)
        self._include = include_prefixes
        self._exclude = exclude_prefixes

    def filter(self, record: logging.LogRecord) -> bool:
        """Return True if *record* passes the prefix filters."""
        name = record.name
        if self._exclude and any(name.startswith(prefix) for prefix in self._exclude):
            return False
        if self._include:
            return any(name.startswith(prefix) for prefix in self._include)
        return True


def _ensure_log_dir(file_path: Path, sink_name: str) -> None:
    """Create parent directories for a log file path.

    Raises:
        RuntimeError: If directory creation fails.
    """
    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        msg = (
            f"Failed to create log directory '{file_path.parent}' "
            f"for sink '{sink_name}': {exc}"
        )
        raise RuntimeError(msg) from exc


def _build_file_handler(
    sink: SinkConfig,
    log_dir: Path,
) -> logging.Handler:
    """Create a file handler with directory creation and rotation.

    Args:
        sink: The FILE sink configuration.
        log_dir: Base directory for log files.

    Returns:
        A configured file handler.

    Raises:
        RuntimeError: If the log directory or file cannot be created.
        ValueError: If ``file_path`` is unexpectedly ``None``.
    """
    if sink.file_path is None:
        msg = (
            "FILE sink is missing 'file_path'. "
            "This should have been caught by SinkConfig validation."
        )
        raise ValueError(msg)

    file_path = log_dir / sink.file_path
    _ensure_log_dir(file_path, sink.file_path)
    rotation = sink.rotation or RotationConfig()

    try:
        if rotation.strategy == RotationStrategy.BUILTIN:
            return _FlushingRotatingFileHandler(
                filename=str(file_path),
                maxBytes=rotation.max_bytes,
                backupCount=rotation.backup_count,
            )
        return _FlushingWatchedFileHandler(filename=str(file_path))
    except OSError as exc:
        msg = (
            f"Failed to open log file '{file_path}' for sink '{sink.file_path}': {exc}"
        )
        raise RuntimeError(msg) from exc


def _build_formatter(
    sink: SinkConfig,
    foreign_pre_chain: list[Any],
) -> ProcessorFormatter:
    """Build a ``ProcessorFormatter`` for the given sink.

    JSON sinks include ``format_exc_info`` to serialize exception tuples.
    Console sinks omit it because ``ConsoleRenderer`` handles exceptions
    natively.
    """
    renderer: Any
    if sink.json_format:
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    processors: list[Any] = [ProcessorFormatter.remove_processors_meta]
    if sink.json_format:
        processors.append(structlog.processors.format_exc_info)
    processors.append(renderer)

    return ProcessorFormatter(
        processors=processors,
        foreign_pre_chain=foreign_pre_chain,
    )


def build_handler(
    sink: SinkConfig,
    log_dir: Path,
    foreign_pre_chain: list[Any],
) -> logging.Handler:
    """Build a stdlib logging handler from a sink configuration.

    For ``CONSOLE`` sinks a :class:`logging.StreamHandler` writing to
    ``stderr`` is created.  For ``FILE`` sinks see
    :func:`_build_file_handler`.

    Args:
        sink: The sink configuration describing the handler to build.
        log_dir: Base directory for log files.
        foreign_pre_chain: Processor chain for stdlib-originated logs.

    Returns:
        A configured :class:`logging.Handler` with formatter attached.
    """
    if sink.sink_type == SinkType.CONSOLE:
        handler: logging.Handler = logging.StreamHandler(sys.stderr)
    else:
        handler = _build_file_handler(sink, log_dir)

    handler.setLevel(sink.level.value)
    handler.setFormatter(_build_formatter(sink, foreign_pre_chain))

    if sink.file_path is not None and sink.file_path in _SINK_ROUTING:
        name_filter = _LoggerNameFilter(
            include_prefixes=_SINK_ROUTING[sink.file_path],
        )
        handler.addFilter(name_filter)

    return handler
