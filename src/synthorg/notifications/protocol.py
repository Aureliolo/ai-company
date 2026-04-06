"""NotificationSink protocol for external notification delivery."""

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from synthorg.notifications.models import Notification


@runtime_checkable
class NotificationSink(Protocol):
    """Protocol for notification delivery adapters.

    Implementations should log errors internally and re-raise so
    the ``NotificationDispatcher`` can track delivery status.
    ``MemoryError`` and ``RecursionError`` must always propagate.

    The ``sink_name`` property is used for logging and diagnostics.
    """

    @property
    def sink_name(self) -> str:
        """Human-readable sink identifier for logging."""
        ...

    async def send(self, notification: Notification) -> None:
        """Deliver a notification.

        Implementations should log errors internally and re-raise
        so ``NotificationDispatcher`` can track delivery status.
        ``MemoryError`` and ``RecursionError`` must always propagate.

        Args:
            notification: The notification to deliver.
        """
        ...
