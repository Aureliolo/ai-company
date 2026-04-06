"""NotificationSink protocol for external notification delivery."""

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from synthorg.notifications.models import Notification


@runtime_checkable
class NotificationSink(Protocol):
    """Protocol for notification delivery adapters.

    All implementations must be async and best-effort: failures
    are logged internally and never crash the caller.

    The ``sink_name`` property is used for logging and diagnostics.
    """

    @property
    def sink_name(self) -> str:
        """Human-readable sink identifier for logging."""
        ...

    async def send(self, notification: Notification) -> None:
        """Deliver a notification.

        Implementations MUST NOT raise -- errors are logged
        internally and swallowed.

        Args:
            notification: The notification to deliver.
        """
        ...
