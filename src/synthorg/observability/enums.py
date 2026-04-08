"""Observability-specific enumerations."""

from enum import StrEnum


class LogLevel(StrEnum):
    """Standard log severity levels.

    Values match Python's stdlib logging level names for seamless
    integration between structlog and the ``logging`` module.
    """

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class RotationStrategy(StrEnum):
    """Log file rotation strategies.

    Attributes:
        BUILTIN: Size-based rotation via ``RotatingFileHandler``.
        EXTERNAL: Watched rotation via ``WatchedFileHandler`` (logrotate).
    """

    BUILTIN = "builtin"
    EXTERNAL = "external"


class SinkType(StrEnum):
    """Log output destination types.

    Attributes:
        CONSOLE: Write to stderr via ``StreamHandler``.
        FILE: Write to a log file with optional rotation.
        SYSLOG: Ship structured JSON to a syslog endpoint.
        HTTP: POST JSON log batches to an HTTP endpoint.
        PROMETHEUS: Prometheus metrics scrape endpoint (pull-based).
        OTLP: OpenTelemetry Protocol log/trace exporter (push-based).
    """

    CONSOLE = "console"
    FILE = "file"
    SYSLOG = "syslog"
    HTTP = "http"
    PROMETHEUS = "prometheus"
    OTLP = "otlp"


class OtlpProtocol(StrEnum):
    """OpenTelemetry Protocol transport.

    Attributes:
        HTTP_JSON: HTTP with JSON encoding (the only implemented transport).
        GRPC: gRPC transport (not implemented; rejected at handler init).
    """

    HTTP_JSON = "http/json"
    GRPC = "grpc"


class SyslogFacility(StrEnum):
    """Syslog facility codes.

    Maps to ``logging.handlers.SysLogHandler.LOG_*`` constants.
    """

    USER = "user"
    LOCAL0 = "local0"
    LOCAL1 = "local1"
    LOCAL2 = "local2"
    LOCAL3 = "local3"
    LOCAL4 = "local4"
    LOCAL5 = "local5"
    LOCAL6 = "local6"
    LOCAL7 = "local7"
    DAEMON = "daemon"
    SYSLOG = "syslog"
    AUTH = "auth"
    KERN = "kern"


class SyslogProtocol(StrEnum):
    """Syslog transport protocol.

    Attributes:
        TCP: Reliable delivery via ``socket.SOCK_STREAM``.
        UDP: Lightweight delivery via ``socket.SOCK_DGRAM``.
    """

    TCP = "tcp"
    UDP = "udp"
