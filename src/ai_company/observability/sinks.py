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


def build_handler(
    sink: SinkConfig,
    log_dir: Path,
    foreign_pre_chain: list[Any],
) -> logging.Handler:
    """Build a stdlib logging handler from a sink configuration.

    For ``CONSOLE`` sinks a :class:`logging.StreamHandler` writing to
    ``stderr`` is created.  For ``FILE`` sinks the handler type depends
    on the rotation strategy:

    - ``BUILTIN`` → :class:`~logging.handlers.RotatingFileHandler`
    - ``EXTERNAL`` → :class:`~logging.handlers.WatchedFileHandler`

    Parent directories for file sinks are created automatically.

    Args:
        sink: The sink configuration describing the handler to build.
        log_dir: Base directory for log files.
        foreign_pre_chain: Processor chain for stdlib-originated logs.

    Returns:
        A configured :class:`logging.Handler` with formatter attached.
    """
    handler: logging.Handler

    if sink.sink_type == SinkType.CONSOLE:
        handler = logging.StreamHandler(sys.stderr)
    else:
        # Guaranteed non-None by SinkConfig validator
        assert sink.file_path is not None  # noqa: S101
        file_path = log_dir / sink.file_path
        file_path.parent.mkdir(parents=True, exist_ok=True)

        rotation = sink.rotation or RotationConfig()

        if rotation.strategy == RotationStrategy.BUILTIN:
            handler = logging.handlers.RotatingFileHandler(
                filename=str(file_path),
                maxBytes=rotation.max_bytes,
                backupCount=rotation.backup_count,
            )
        else:
            handler = logging.handlers.WatchedFileHandler(
                filename=str(file_path),
            )

    handler.setLevel(sink.level.value)

    renderer: Any
    if sink.json_format:
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    formatter = ProcessorFormatter(
        processors=[renderer],
        foreign_pre_chain=foreign_pre_chain,
    )
    handler.setFormatter(formatter)

    return handler
