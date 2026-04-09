"""Telemetry configuration model."""

from enum import StrEnum, unique

from pydantic import BaseModel, ConfigDict, Field

from synthorg.core.types import NotBlankStr  # noqa: TC001 -- Pydantic needs at runtime


@unique
class TelemetryBackend(StrEnum):
    """Supported telemetry reporter backends."""

    LOGFIRE = "logfire"
    NOOP = "noop"


class TelemetryConfig(BaseModel):
    """Configuration for opt-in anonymous product telemetry.

    Telemetry is **disabled by default**.  When enabled, only
    aggregate usage metrics are sent -- never API keys, chat
    content, or personal data.

    Attributes:
        enabled: Master switch (default ``False``).  Can be
            overridden by ``SYNTHORG_TELEMETRY`` env var.
        backend: Reporter backend to use.
        heartbeat_interval_hours: Hours between periodic heartbeat
            events.
        token: Write token for the telemetry backend.  When
            ``None``, the embedded default project token is used.
            Can be overridden by ``SYNTHORG_TELEMETRY_TOKEN`` env
            var (useful for self-hosted backends).
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    enabled: bool = Field(
        default=False,
        description="Enable anonymous product telemetry (default: off)",
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
    token: NotBlankStr | None = Field(
        default=None,
        repr=False,
        description="Backend write token override (None = embedded default)",
    )
