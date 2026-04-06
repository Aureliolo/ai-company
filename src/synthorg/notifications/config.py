"""Notification subsystem configuration."""

from pydantic import BaseModel, ConfigDict, Field

from synthorg.core.types import NotBlankStr  # noqa: TC001
from synthorg.notifications.models import NotificationSeverity


class NotificationSinkConfig(BaseModel):
    """Configuration for a single notification sink.

    Attributes:
        type: Adapter type (``console``, ``ntfy``, ``slack``,
            ``email``).
        enabled: Whether this sink is active.
        params: Adapter-specific parameters (URL, topic, etc.).
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    type: NotBlankStr = Field(description="Adapter type")
    enabled: bool = Field(
        default=True,
        description="Whether this sink is active",
    )
    params: dict[str, str] = Field(
        default_factory=dict,
        description="Adapter-specific parameters",
    )


class NotificationConfig(BaseModel):
    """Notification subsystem configuration.

    Attributes:
        sinks: Configured notification sinks.
        min_severity: Minimum severity to dispatch (filters below).
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    sinks: tuple[NotificationSinkConfig, ...] = Field(
        default=(NotificationSinkConfig(type="console"),),
        description="Configured notification sinks",
    )
    min_severity: NotificationSeverity = Field(
        default=NotificationSeverity.INFO,
        description="Minimum severity to dispatch",
    )
