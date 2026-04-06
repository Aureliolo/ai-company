"""Notification domain models.

The ``Notification`` model defines the event taxonomy shared with
the frontend's ``NotificationItem`` TypeScript type (#1078).
Changes to categories or severity levels MUST be mirrored in
``web/src/types/notifications.ts``.
"""

from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from synthorg.core.types import NotBlankStr  # noqa: TC001


class NotificationCategory(StrEnum):
    """Notification event categories.

    Shared with frontend ``NotificationItem.category``.
    """

    APPROVAL = "approval"
    BUDGET = "budget"
    SECURITY = "security"
    STAGNATION = "stagnation"
    SYSTEM = "system"
    AGENT = "agent"


class NotificationSeverity(StrEnum):
    """Notification severity levels.

    Shared with frontend ``NotificationItem.severity``.
    """

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class Notification(BaseModel):
    """An operator notification event.

    Frozen Pydantic model delivered via registered sinks. The
    ``category`` and ``severity`` fields form the shared event
    taxonomy with the frontend notification system (#1078).

    Attributes:
        id: Unique notification identifier.
        category: Event category for filtering and routing.
        severity: Severity level.
        title: Human-readable summary (one line).
        body: Detailed notification body.
        source: Originating subsystem (e.g. ``"budget.enforcer"``).
        timestamp: When the event occurred (UTC).
        metadata: Arbitrary structured context for adapters.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    id: NotBlankStr = Field(
        default_factory=lambda: str(uuid4()),
        description="Unique notification identifier",
    )
    category: NotificationCategory = Field(
        description="Event category for filtering and routing",
    )
    severity: NotificationSeverity = Field(
        description="Severity level",
    )
    title: NotBlankStr = Field(
        description="Human-readable summary (one line)",
    )
    body: str = Field(
        default="",
        description="Detailed notification body",
    )
    source: NotBlankStr = Field(
        description="Originating subsystem",
    )
    timestamp: AwareDatetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="When the event occurred (UTC)",
    )
    metadata: dict[str, object] = Field(
        default_factory=dict,
        description="Arbitrary structured context for adapters",
    )
