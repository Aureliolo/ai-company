"""Telemetry configuration model."""

from enum import StrEnum, unique

from pydantic import BaseModel, ConfigDict, Field


@unique
class TelemetryBackend(StrEnum):
    """Supported telemetry reporter backends."""

    LOGFIRE = "logfire"
    NOOP = "noop"


class TelemetryConfig(BaseModel):
    """Configuration for opt-in anonymous project telemetry.

    Telemetry is **disabled by default**. When enabled, only
    aggregate usage metrics are sent -- never API keys, chat
    content, or personal data. Telemetry is SynthOrg-owned and
    project-scoped: the write token is embedded in source and
    cannot be redirected to a different backend. Operators that
    need their own observability stack use the Postgres +
    Prometheus + audit-chain path, not this module.

    Attributes:
        enabled: Master switch (default ``False``). Can be
            overridden by the ``SYNTHORG_TELEMETRY`` env var.
        backend: Reporter backend to use.
        heartbeat_interval_hours: Hours between periodic heartbeat
            events.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False, extra="forbid")

    enabled: bool = Field(
        default=False,
        description="Enable anonymous project telemetry (default: off)",
    )
    backend: TelemetryBackend = Field(
        default=TelemetryBackend.LOGFIRE,
        description="Telemetry reporter backend",
    )
    heartbeat_interval_hours: float = Field(
        default=6.0,
        gt=0.0,
        le=168.0,
        description="Hours between heartbeat events (1h--168h)",
    )
