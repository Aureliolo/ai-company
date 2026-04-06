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
    NOTIFICATION_NO_SINKS,
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

    ``register()`` is only safe to call before the event loop
    starts processing requests.

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

        Args:
            notification: The notification to deliver.
        """
        # Snapshot the sink list so register() during dispatch is safe.
        sinks = list(self._sinks)
        if not sinks:
            logger.debug(
                NOTIFICATION_NO_SINKS,
                notification_id=notification.id,
            )
            return

        if self._should_filter(notification):
            return

        errors: list[str | None] = [None] * len(sinks)
        try:
            async with asyncio.TaskGroup() as tg:
                for idx, sink in enumerate(sinks):
                    tg.create_task(
                        self._guarded_send(sink, notification, errors, idx),
                    )
        except ExceptionGroup as eg:
            for exc in eg.exceptions:
                if isinstance(exc, MemoryError | RecursionError):
                    raise exc from eg
            self._log_exception_group(notification, errors, eg)
            return

        self._log_result(notification, errors)

    async def close(self) -> None:
        """Close all sinks that support cleanup."""
        for sink in self._sinks:
            if hasattr(sink, "close"):
                try:
                    await sink.close()
                except MemoryError, RecursionError:
                    raise
                except Exception:
                    logger.warning(
                        NOTIFICATION_DISPATCH_FAILED,
                        sink_name=sink.sink_name,
                        error="close() failed",
                        exc_info=True,
                    )

    def _should_filter(self, notification: Notification) -> bool:
        """Return True if the notification is below min_severity."""
        if _SEVERITY_ORDER[notification.severity] < _SEVERITY_ORDER[self._min_severity]:
            logger.debug(
                NOTIFICATION_FILTERED,
                notification_id=notification.id,
                severity=notification.severity,
                min_severity=self._min_severity,
            )
            return True
        return False

    def _log_result(
        self,
        notification: Notification,
        errors: list[str | None],
    ) -> None:
        """Log dispatch outcome after TaskGroup completes."""
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
                sinks=len(errors),
            )

    def _log_exception_group(
        self,
        notification: Notification,
        errors: list[str | None],
        eg: ExceptionGroup,
    ) -> None:
        """Log ExceptionGroup with per-sink context preserved."""
        partial_errors = [e for e in errors if e is not None]
        logger.warning(
            NOTIFICATION_DISPATCH_FAILED,
            notification_id=notification.id,
            category=notification.category,
            error=f"TaskGroup errors: {eg.exceptions}",
            partial_sink_errors=partial_errors,
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
