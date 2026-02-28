"""Logging system setup and configuration.

Provides the idempotent :func:`configure_logging` entry point that
wires structlog processors, stdlib handlers, and per-logger levels.
"""

import logging
from pathlib import Path
from typing import Any

import structlog

from ai_company.observability.config import DEFAULT_SINKS, LogConfig
from ai_company.observability.enums import LogLevel
from ai_company.observability.processors import sanitize_sensitive_fields
from ai_company.observability.sinks import build_handler

# Default per-logger levels applied when no config overrides are given.
_DEFAULT_LOGGER_LEVELS: tuple[tuple[str, LogLevel], ...] = (
    ("ai_company.core", LogLevel.INFO),
    ("ai_company.engine", LogLevel.DEBUG),
    ("ai_company.communication", LogLevel.INFO),
    ("ai_company.providers", LogLevel.INFO),
    ("ai_company.budget", LogLevel.INFO),
    ("ai_company.security", LogLevel.INFO),
    ("ai_company.memory", LogLevel.DEBUG),
    ("ai_company.tools", LogLevel.INFO),
    ("ai_company.api", LogLevel.INFO),
    ("ai_company.cli", LogLevel.INFO),
    ("ai_company.config", LogLevel.INFO),
    ("ai_company.templates", LogLevel.INFO),
)


def _build_shared_processors() -> list[Any]:
    """Build the shared processor chain for foreign (stdlib) logs.

    Returns:
        A list of structlog processors applied to stdlib-originated
        log records before the final renderer.
    """
    return [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        sanitize_sensitive_fields,
    ]


def configure_logging(config: LogConfig | None = None) -> None:
    """Configure the structured logging system.

    Sets up structlog processor chains, stdlib handlers, and per-logger
    levels.  This function is **idempotent** — calling it multiple times
    replaces the previous configuration without duplicating handlers.

    Args:
        config: Logging configuration.  When ``None``, uses sensible
            defaults with all standard sinks.
    """
    if config is None:
        config = LogConfig(sinks=DEFAULT_SINKS)

    # 1. Reset structlog to a clean state
    structlog.reset_defaults()

    # 2. Clear existing stdlib root handlers
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
        handler.close()

    # 3. Set root logger to DEBUG so handlers can filter individually
    root_logger.setLevel(logging.DEBUG)

    # 4. Build shared processor chain (foreign pre-chain)
    shared_processors = _build_shared_processors()

    # 5. Configure structlog main chain (for structlog-originated logs)
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            sanitize_sensitive_fields,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # 6. Build and attach handlers for each sink
    log_dir = Path(config.log_dir)
    for sink in config.sinks:
        handler = build_handler(
            sink=sink,
            log_dir=log_dir,
            foreign_pre_chain=shared_processors,
        )
        root_logger.addHandler(handler)

    # 7. Apply default named logger levels
    for name, level in _DEFAULT_LOGGER_LEVELS:
        logging.getLogger(name).setLevel(level.value)

    # 8. Apply config overrides (take precedence over defaults)
    for name, level in config.logger_levels:
        logging.getLogger(name).setLevel(level.value)
