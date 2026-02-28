"""Log handler factory for building stdlib handlers from sink config.

Translates :class:`~ai_company.observability.config.SinkConfig` instances
into fully configured :class:`logging.Handler` objects with the
appropriate structlog :class:`~structlog.stdlib.ProcessorFormatter`.
"""

# TODO: Add logger name filters to route specific loggers to specific
# sinks (e.g., security -> audit.log)

import logging
import logging.handlers
import sys
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

import structlog
from structlog.stdlib import ProcessorFormatter

from ai_company.observability.config import RotationConfig, SinkConfig
from ai_company.observability.enums import RotationStrategy, SinkType


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

    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        msg = (
            f"Failed to create log directory '{file_path.parent}' "
            f"for sink '{sink.file_path}': {exc}"
        )
        raise RuntimeError(msg) from exc

    rotation = sink.rotation or RotationConfig()

    try:
        if rotation.strategy == RotationStrategy.BUILTIN:
            return logging.handlers.RotatingFileHandler(
                filename=str(file_path),
                maxBytes=rotation.max_bytes,
                backupCount=rotation.backup_count,
            )
        return logging.handlers.WatchedFileHandler(
            filename=str(file_path),
        )
    except OSError as exc:
        msg = (
            f"Failed to open log file '{file_path}' for sink '{sink.file_path}': {exc}"
        )
        raise RuntimeError(msg) from exc


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

    renderer: Any
    if sink.json_format:
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    formatter = ProcessorFormatter(
        processors=[
            ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
        foreign_pre_chain=foreign_pre_chain,
    )
    handler.setFormatter(formatter)

    return handler
