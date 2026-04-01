"""Observability configuration models.

Frozen Pydantic models for log sinks, rotation, and top-level logging
configuration.  All models are immutable and validated on construction.

.. note::

    ``DEFAULT_SINKS`` provides the standard eleven-sink layout described
    in the design spec (console + ten file sinks).
"""

from collections import Counter
from pathlib import PurePath, PurePosixPath, PureWindowsPath
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from synthorg.core.types import NotBlankStr  # noqa: TC001
from synthorg.observability.enums import (
    LogLevel,
    RotationStrategy,
    SinkType,
    SyslogFacility,
    SyslogProtocol,
)


class RotationConfig(BaseModel):
    """Log file rotation configuration.

    Attributes:
        strategy: Rotation mechanism to use.
        max_bytes: Maximum file size in bytes before rotation.
            Only used when ``strategy`` is
            :attr:`RotationStrategy.BUILTIN`.
        backup_count: Number of rotated backup files to keep.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    strategy: RotationStrategy = Field(
        default=RotationStrategy.BUILTIN,
        description="Rotation mechanism",
    )
    max_bytes: int = Field(
        default=10 * 1024 * 1024,
        gt=0,
        description="Maximum file size in bytes before rotation",
    )
    backup_count: int = Field(
        default=5,
        ge=0,
        description="Number of rotated backup files to keep",
    )
    compress_rotated: bool = Field(
        default=False,
        description="Gzip-compress rotated backup files",
    )


class SinkConfig(BaseModel):
    """Configuration for a single log output destination.

    Attributes:
        sink_type: Where to send log output.
        level: Minimum log level for this sink.
        file_path: Relative path for FILE sinks (within ``log_dir``).
        rotation: Rotation settings for FILE sinks.
        json_format: Whether to format output as JSON.
        syslog_host: Hostname for SYSLOG sinks.
        syslog_port: Port for SYSLOG sinks.
        syslog_facility: Syslog facility code.
        syslog_protocol: Transport protocol (TCP or UDP).
        http_url: Endpoint URL for HTTP sinks.
        http_headers: Extra HTTP headers as ``(name, value)`` pairs.
        http_batch_size: Records per HTTP POST batch.
        http_flush_interval_seconds: Seconds between automatic flushes.
        http_timeout_seconds: HTTP request timeout.
        http_max_retries: Retry count on HTTP failure.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    sink_type: SinkType = Field(
        description="Log output destination type",
    )
    level: LogLevel = Field(
        default=LogLevel.INFO,
        description="Minimum log level for this sink",
    )
    # FILE fields
    file_path: str | None = Field(
        default=None,
        description="Relative path for FILE sinks (within log_dir)",
    )
    rotation: RotationConfig | None = Field(
        default=None,
        description="Rotation settings for FILE sinks",
    )
    json_format: bool = Field(
        default=True,
        description="Whether to format output as JSON",
    )
    # SYSLOG fields
    syslog_host: str | None = Field(
        default=None,
        description="Hostname for SYSLOG sinks",
    )
    syslog_port: int = Field(
        default=514,
        gt=0,
        le=65535,
        description="Port for SYSLOG sinks",
    )
    syslog_facility: SyslogFacility = Field(
        default=SyslogFacility.USER,
        description="Syslog facility code",
    )
    syslog_protocol: SyslogProtocol = Field(
        default=SyslogProtocol.UDP,
        description="Transport protocol (TCP or UDP)",
    )
    # HTTP fields
    http_url: str | None = Field(
        default=None,
        description="Endpoint URL for HTTP sinks",
    )
    http_headers: tuple[tuple[str, str], ...] = Field(
        default=(),
        description="Extra HTTP headers as (name, value) pairs",
    )
    http_batch_size: int = Field(
        default=100,
        gt=0,
        description="Records per HTTP POST batch",
    )
    http_flush_interval_seconds: float = Field(
        default=5.0,
        gt=0,
        description="Seconds between automatic flushes",
    )
    http_timeout_seconds: float = Field(
        default=10.0,
        gt=0,
        description="HTTP request timeout in seconds",
    )
    http_max_retries: int = Field(
        default=3,
        ge=0,
        description="Retry count on HTTP failure",
    )

    @model_validator(mode="after")
    def _validate_sink_type_fields(self) -> Self:
        """Enforce required/rejected fields per sink type."""
        match self.sink_type:
            case SinkType.FILE:
                self._validate_file_fields()
            case SinkType.CONSOLE:
                self._reject_file_fields("CONSOLE")
                self._reject_syslog_fields("CONSOLE")
                self._reject_http_fields("CONSOLE")
            case SinkType.SYSLOG:
                self._reject_file_fields("SYSLOG")
                self._validate_syslog_fields()
                self._reject_http_fields("SYSLOG")
            case SinkType.HTTP:
                self._reject_file_fields("HTTP")
                self._reject_syslog_fields("HTTP")
                self._validate_http_fields()
        return self

    def _validate_file_fields(self) -> None:
        if self.file_path is None:
            msg = "file_path is required for FILE sinks"
            raise ValueError(msg)
        if not self.file_path.strip():
            msg = "file_path must not be empty or whitespace-only"
            raise ValueError(msg)
        path = PurePath(self.file_path)
        if (
            path.is_absolute()
            or PurePosixPath(self.file_path).is_absolute()
            or PureWindowsPath(self.file_path).is_absolute()
        ):
            msg = f"file_path must be relative: {self.file_path}"
            raise ValueError(msg)
        if ".." in path.parts:
            msg = f"file_path must not contain '..' components: {self.file_path}"
            raise ValueError(msg)
        self._reject_syslog_fields("FILE")
        self._reject_http_fields("FILE")

    def _reject_file_fields(self, sink_label: str) -> None:
        if self.file_path is not None:
            msg = f"file_path must be None for {sink_label} sinks"
            raise ValueError(msg)
        if self.rotation is not None:
            msg = f"rotation must be None for {sink_label} sinks"
            raise ValueError(msg)

    def _validate_syslog_fields(self) -> None:
        if self.syslog_host is None:
            msg = "syslog_host is required for SYSLOG sinks"
            raise ValueError(msg)
        if not self.syslog_host.strip():
            msg = "syslog_host must not be blank"
            raise ValueError(msg)

    def _reject_syslog_fields(self, sink_label: str) -> None:
        if self.syslog_host is not None:
            msg = f"syslog_host must be None for {sink_label} sinks"
            raise ValueError(msg)

    def _validate_http_fields(self) -> None:
        if self.http_url is None:
            msg = "http_url is required for HTTP sinks"
            raise ValueError(msg)
        if not self.http_url.strip():
            msg = "http_url must not be blank"
            raise ValueError(msg)
        if not (
            self.http_url.startswith("http://") or self.http_url.startswith("https://")
        ):
            msg = "http_url must start with http:// or https://"
            raise ValueError(msg)

    def _reject_http_fields(self, sink_label: str) -> None:
        if self.http_url is not None:
            msg = f"http_url must be None for {sink_label} sinks"
            raise ValueError(msg)


class LogConfig(BaseModel):
    """Top-level logging configuration.

    Attributes:
        root_level: Root logger level (handlers filter individually).
        logger_levels: Per-logger level overrides as ``(name, level)`` pairs.
        sinks: Tuple of sink configurations.
        enable_correlation: Whether to enable correlation ID tracking.
        log_dir: Directory for log files.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    root_level: LogLevel = Field(
        default=LogLevel.DEBUG,
        description="Root logger level",
    )
    logger_levels: tuple[tuple[NotBlankStr, LogLevel], ...] = Field(
        default=(),
        description="Per-logger level overrides as (name, level) pairs",
    )
    sinks: tuple[SinkConfig, ...] = Field(
        description="Log output destinations",
    )
    enable_correlation: bool = Field(
        default=True,
        description="Whether to enable correlation ID tracking",
    )
    log_dir: NotBlankStr = Field(
        default="logs",
        description="Directory for log files",
    )

    @model_validator(mode="after")
    def _validate_at_least_one_sink(self) -> Self:
        """Ensure at least one sink is configured."""
        if not self.sinks:
            msg = "At least one sink must be configured"
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _validate_no_duplicate_logger_names(self) -> Self:
        """Ensure no duplicate logger names in ``logger_levels``."""
        names = [name for name, _ in self.logger_levels]
        counts = Counter(names)
        dupes = sorted(n for n, c in counts.items() if c > 1)
        if dupes:
            msg = f"Duplicate logger names in logger_levels: {dupes}"
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _validate_no_duplicate_file_paths(self) -> Self:
        """Ensure no duplicate file paths across FILE sinks."""
        paths = [
            s.file_path
            for s in self.sinks
            if s.sink_type == SinkType.FILE and s.file_path is not None
        ]
        counts = Counter(paths)
        dupes = sorted(p for p, c in counts.items() if c > 1)
        if dupes:
            msg = f"Duplicate file paths across sinks: {dupes}"
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _validate_no_duplicate_syslog_endpoints(self) -> Self:
        """Ensure no duplicate syslog ``(host, port)`` pairs."""
        endpoints = [
            (s.syslog_host, s.syslog_port)
            for s in self.sinks
            if s.sink_type == SinkType.SYSLOG
        ]
        counts = Counter(endpoints)
        dupes = sorted(f"{h}:{p}" for (h, p), c in counts.items() if c > 1)
        if dupes:
            msg = f"Duplicate syslog endpoints: {dupes}"
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _validate_no_duplicate_http_urls(self) -> Self:
        """Ensure no duplicate HTTP URLs."""
        urls = [
            s.http_url
            for s in self.sinks
            if s.sink_type == SinkType.HTTP and s.http_url is not None
        ]
        counts = Counter(urls)
        dupes = sorted(u for u, c in counts.items() if c > 1)
        if dupes:
            msg = f"Duplicate HTTP URLs: {dupes}"
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _validate_log_dir_safe(self) -> Self:
        """Ensure ``log_dir`` has no path traversal."""
        path = PurePath(self.log_dir)
        if ".." in path.parts:
            msg = f"log_dir must not contain '..' components: {self.log_dir}"
            raise ValueError(msg)
        return self


DEFAULT_SINKS: tuple[SinkConfig, ...] = (
    SinkConfig(
        sink_type=SinkType.CONSOLE,
        level=LogLevel.INFO,
        json_format=False,
    ),
    SinkConfig(
        sink_type=SinkType.FILE,
        level=LogLevel.INFO,
        file_path="synthorg.log",
        rotation=RotationConfig(),
        json_format=True,
    ),
    SinkConfig(
        sink_type=SinkType.FILE,
        level=LogLevel.INFO,
        file_path="audit.log",
        rotation=RotationConfig(),
        json_format=True,
    ),
    SinkConfig(
        sink_type=SinkType.FILE,
        level=LogLevel.ERROR,
        file_path="errors.log",
        rotation=RotationConfig(),
        json_format=True,
    ),
    SinkConfig(
        sink_type=SinkType.FILE,
        level=LogLevel.DEBUG,
        file_path="agent_activity.log",
        rotation=RotationConfig(),
        json_format=True,
    ),
    SinkConfig(
        sink_type=SinkType.FILE,
        level=LogLevel.INFO,
        file_path="cost_usage.log",
        rotation=RotationConfig(),
        json_format=True,
    ),
    SinkConfig(
        sink_type=SinkType.FILE,
        level=LogLevel.DEBUG,
        file_path="debug.log",
        rotation=RotationConfig(),
        json_format=True,
    ),
    SinkConfig(
        sink_type=SinkType.FILE,
        level=LogLevel.INFO,
        file_path="access.log",
        rotation=RotationConfig(),
        json_format=True,
    ),
    SinkConfig(
        sink_type=SinkType.FILE,
        level=LogLevel.INFO,
        file_path="persistence.log",
        rotation=RotationConfig(),
        json_format=True,
    ),
    SinkConfig(
        sink_type=SinkType.FILE,
        level=LogLevel.INFO,
        file_path="configuration.log",
        rotation=RotationConfig(),
        json_format=True,
    ),
    SinkConfig(
        sink_type=SinkType.FILE,
        level=LogLevel.INFO,
        file_path="backup.log",
        rotation=RotationConfig(),
        json_format=True,
    ),
)
