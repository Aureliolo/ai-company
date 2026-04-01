"""Syslog handler builder for shipping structured logs to syslog endpoints.

Builds a ``logging.handlers.SysLogHandler`` configured for structured
JSON output via structlog's ``ProcessorFormatter``.
"""

import logging.handlers
import socket
from types import MappingProxyType
from typing import TYPE_CHECKING, Any

import structlog
from structlog.stdlib import ProcessorFormatter

from synthorg.observability.enums import SyslogFacility, SyslogProtocol

if TYPE_CHECKING:
    from synthorg.observability.config import SinkConfig

FACILITY_MAP: MappingProxyType[SyslogFacility, int] = MappingProxyType(
    {
        SyslogFacility.USER: logging.handlers.SysLogHandler.LOG_USER,
        SyslogFacility.DAEMON: logging.handlers.SysLogHandler.LOG_DAEMON,
        SyslogFacility.SYSLOG: logging.handlers.SysLogHandler.LOG_SYSLOG,
        SyslogFacility.AUTH: logging.handlers.SysLogHandler.LOG_AUTH,
        SyslogFacility.KERN: logging.handlers.SysLogHandler.LOG_KERN,
        SyslogFacility.LOCAL0: logging.handlers.SysLogHandler.LOG_LOCAL0,
        SyslogFacility.LOCAL1: logging.handlers.SysLogHandler.LOG_LOCAL1,
        SyslogFacility.LOCAL2: logging.handlers.SysLogHandler.LOG_LOCAL2,
        SyslogFacility.LOCAL3: logging.handlers.SysLogHandler.LOG_LOCAL3,
        SyslogFacility.LOCAL4: logging.handlers.SysLogHandler.LOG_LOCAL4,
        SyslogFacility.LOCAL5: logging.handlers.SysLogHandler.LOG_LOCAL5,
        SyslogFacility.LOCAL6: logging.handlers.SysLogHandler.LOG_LOCAL6,
        SyslogFacility.LOCAL7: logging.handlers.SysLogHandler.LOG_LOCAL7,
    }
)

PROTOCOL_MAP: MappingProxyType[SyslogProtocol, int] = MappingProxyType(
    {
        SyslogProtocol.TCP: socket.SOCK_STREAM,
        SyslogProtocol.UDP: socket.SOCK_DGRAM,
    }
)


def build_syslog_handler(
    sink: SinkConfig,
    foreign_pre_chain: list[Any],
) -> logging.handlers.SysLogHandler:
    """Build a SysLogHandler from a SYSLOG sink configuration.

    Args:
        sink: The SYSLOG sink configuration.
        foreign_pre_chain: Processor chain for stdlib-originated logs.

    Returns:
        A configured ``SysLogHandler`` with JSON formatting.
    """
    if not sink.syslog_host:
        msg = "SYSLOG sink requires a non-empty syslog_host"
        raise ValueError(msg)
    handler = logging.handlers.SysLogHandler(
        address=(sink.syslog_host, sink.syslog_port),
        facility=FACILITY_MAP[sink.syslog_facility],
        socktype=socket.SocketKind(PROTOCOL_MAP[sink.syslog_protocol]),
    )
    handler.setLevel(sink.level.value)

    renderer: Any = structlog.processors.JSONRenderer()
    processors: list[Any] = [
        ProcessorFormatter.remove_processors_meta,
        structlog.processors.format_exc_info,
        renderer,
    ]
    formatter = ProcessorFormatter(
        processors=processors,
        foreign_pre_chain=foreign_pre_chain,
    )
    handler.setFormatter(formatter)

    return handler
