"""Notification dispatcher -- fan-out to registered sinks."""

import asyncio
from typing import TYPE_CHECKING

from synthorg.notifications.models import (
    Notification,
    NotificationSeverity,
)
from synthorg.observability import get_logger
from synthorg.observability.events.notification import (
    NOTIFICATION_DISPATCH_FAILED,
    NOTIFICATION_DISPATCHED,
    NOTIFICATION_FILTERED,
    NOTIFICATION_SINK_REGISTERED,
)

if TYPE_CHECKING:
    from synthorg.notifications.protocol import NotificationSink

logger = get_logger(__name__)

_SEVERITY_ORDER: dict[NotificationSeverity, int] = {
    NotificationSeverity.INFO: 0,
    NotificationSeverity.WARNING: 1,
    NotificationSeverity.ERROR: 2,
    NotificationSeverity.CRITICAL: 3,
}


class NotificationDispatcher:
    """Fan-out notifications to all registered sinks.

    Best-effort delivery: individual sink failures are logged and
    swallowed. Uses ``asyncio.TaskGroup`` for concurrent delivery.

    Notifications below ``min_severity`` are silently filtered.

    Args:
        sinks: Initial set of notification sinks.
        min_severity: Minimum severity to dispatch.
    """

    __slots__ = ("_min_severity", "_sinks")

    def __init__(
        self,
        sinks: tuple[NotificationSink, ...] = (),
        *,
        min_severity: NotificationSeverity = NotificationSeverity.INFO,
    ) -> None:
        self._sinks = list(sinks)
        self._min_severity = min_severity
        for sink in sinks:
            logger.info(
                NOTIFICATION_SINK_REGISTERED,
                sink_name=sink.sink_name,
            )

    def register(self, sink: NotificationSink) -> None:
        """Register an additional sink.

        Args:
            sink: Notification sink to add.
        """
        self._sinks.append(sink)
        logger.info(
            NOTIFICATION_SINK_REGISTERED,
            sink_name=sink.sink_name,
        )

    async def dispatch(self, notification: Notification) -> None:
        """Deliver a notification to all registered sinks.

        Best-effort: individual sink errors are logged and
        swallowed. ``MemoryError`` and ``RecursionError`` propagate.

        Notifications below the configured ``min_severity`` are
        silently filtered.

        Args:
            notification: The notification to deliver.
        """
        if not self._sinks:
            return

        if _SEVERITY_ORDER[notification.severity] < _SEVERITY_ORDER[self._min_severity]:
            logger.debug(
                NOTIFICATION_FILTERED,
                notification_id=notification.id,
                severity=notification.severity,
                min_severity=self._min_severity,
            )
            return

        errors: list[str | None] = [None] * len(self._sinks)

        async with asyncio.TaskGroup() as tg:
            for idx, sink in enumerate(self._sinks):
                tg.create_task(
                    self._guarded_send(sink, notification, errors, idx),
                )

        failed = sum(1 for e in errors if e is not None)
        if failed:
            logger.warning(
                NOTIFICATION_DISPATCH_FAILED,
                notification_id=notification.id,
                category=notification.category,
                total_sinks=len(self._sinks),
                failed=failed,
            )
        else:
            logger.debug(
                NOTIFICATION_DISPATCHED,
                notification_id=notification.id,
                category=notification.category,
                sinks=len(self._sinks),
            )

    @staticmethod
    async def _guarded_send(
        sink: NotificationSink,
        notification: Notification,
        errors: list[str | None],
        index: int,
    ) -> None:
        """Send to a single sink, capturing errors."""
        try:
            await sink.send(notification)
        except MemoryError, RecursionError:
            raise
        except Exception as exc:
            errors[index] = str(exc)
            logger.warning(
                NOTIFICATION_DISPATCH_FAILED,
                notification_id=notification.id,
                sink_name=sink.sink_name,
                error=str(exc),
                exc_info=True,
            )
