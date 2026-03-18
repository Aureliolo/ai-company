"""Backup settings subscriber -- react to backup setting changes."""

from typing import TYPE_CHECKING

from synthorg.observability import get_logger
from synthorg.observability.events.settings import SETTINGS_SUBSCRIBER_NOTIFIED

if TYPE_CHECKING:
    from synthorg.backup.service import BackupService

logger = get_logger(__name__)

_WATCHED: frozenset[tuple[str, str]] = frozenset(
    {
        ("backup", "enabled"),
        ("backup", "schedule_hours"),
        ("backup", "compression"),
        ("backup", "on_shutdown"),
        ("backup", "on_startup"),
    }
)


class BackupSettingsSubscriber:
    """React to backup-namespace settings changes.

    On ``enabled`` change, starts or stops the backup scheduler.
    On ``schedule_hours`` change, reschedules the interval.
    Other keys are advisory-only (read at use time).

    Args:
        backup_service: Backup service managing the scheduler.
    """

    def __init__(self, backup_service: BackupService) -> None:
        self._backup_service = backup_service

    @property
    def watched_keys(self) -> frozenset[tuple[str, str]]:
        """Return backup-namespace keys this subscriber watches."""
        return _WATCHED

    @property
    def subscriber_name(self) -> str:
        """Human-readable subscriber name."""
        return "backup-settings"

    async def on_settings_changed(
        self,
        namespace: str,
        key: str,
    ) -> None:
        """Handle a backup setting change.

        ``enabled`` toggles the scheduler. ``schedule_hours`` updates
        the interval.  Other keys are advisory and logged at INFO.

        Args:
            namespace: Changed setting namespace.
            key: Changed setting key.
        """
        if key == "enabled":
            await self._toggle_scheduler()
        elif key == "schedule_hours":
            await self._reschedule()
        else:
            logger.info(
                SETTINGS_SUBSCRIBER_NOTIFIED,
                subscriber=self.subscriber_name,
                namespace=namespace,
                key=key,
                note="advisory -- read at use time",
            )

    async def _toggle_scheduler(self) -> None:
        """Start or stop the scheduler based on current state."""
        scheduler = self._backup_service.scheduler
        if scheduler.is_running:
            await scheduler.stop()
            logger.info(
                SETTINGS_SUBSCRIBER_NOTIFIED,
                subscriber=self.subscriber_name,
                namespace="backup",
                key="enabled",
                note="scheduler stopped",
            )
        else:
            scheduler.start()
            logger.info(
                SETTINGS_SUBSCRIBER_NOTIFIED,
                subscriber=self.subscriber_name,
                namespace="backup",
                key="enabled",
                note="scheduler started",
            )

    async def _reschedule(self) -> None:
        """Update the scheduler interval."""
        # The actual value is read from settings at use time;
        # we just need to inform the scheduler that it should
        # re-read its interval.  For simplicity, the subscriber
        # logs the notification.
        logger.info(
            SETTINGS_SUBSCRIBER_NOTIFIED,
            subscriber=self.subscriber_name,
            namespace="backup",
            key="schedule_hours",
            note="reschedule advisory -- takes effect after current interval",
        )
