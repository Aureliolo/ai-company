"""Backup scheduler -- periodic background backup task."""

import asyncio
import contextlib
from typing import TYPE_CHECKING

from synthorg.backup.models import BackupTrigger
from synthorg.observability import get_logger
from synthorg.observability.events.backup import (
    BACKUP_FAILED,
    BACKUP_SCHEDULER_RESCHEDULED,
    BACKUP_SCHEDULER_STARTED,
    BACKUP_SCHEDULER_STOPPED,
    BACKUP_SCHEDULER_TICK,
)

if TYPE_CHECKING:
    from synthorg.backup.service import BackupService

logger = get_logger(__name__)


class BackupScheduler:
    """Background asyncio task that triggers periodic backups.

    Args:
        service: Backup service to delegate backup creation to.
        interval_hours: Hours between scheduled backups.
    """

    def __init__(self, service: BackupService, interval_hours: int) -> None:
        self._service = service
        self._interval_seconds = interval_hours * 3600
        self._task: asyncio.Task[None] | None = None
        self._wake_event = asyncio.Event()

    @property
    def is_running(self) -> bool:
        """Whether the scheduler loop is currently active."""
        return self._task is not None and not self._task.done()

    def start(self) -> None:
        """Start the background scheduler loop.

        Creates an ``asyncio.Task`` running ``_run_loop``.
        No-op if already running.
        """
        if self.is_running:
            return
        self._wake_event.clear()
        self._task = asyncio.create_task(
            self._run_loop(),
            name="backup-scheduler",
        )
        logger.info(
            BACKUP_SCHEDULER_STARTED,
            interval_hours=self._interval_seconds // 3600,
        )

    async def stop(self) -> None:
        """Cancel the background scheduler and wait for it to finish."""
        if self._task is None:
            return
        self._task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await self._task
        self._task = None
        logger.info(BACKUP_SCHEDULER_STOPPED)

    def reschedule(self, interval_hours: int) -> None:
        """Update the interval and interrupt the current sleep.

        The new interval takes effect immediately by waking the
        sleeping loop.

        Args:
            interval_hours: New interval in hours (must be >= 1).

        Raises:
            ValueError: If interval_hours is less than 1.
        """
        if interval_hours < 1:
            msg = "interval_hours must be >= 1"
            raise ValueError(msg)
        self._interval_seconds = interval_hours * 3600
        self._wake_event.set()
        logger.info(
            BACKUP_SCHEDULER_RESCHEDULED,
            interval_hours=interval_hours,
        )

    async def _run_loop(self) -> None:
        """Sleep-and-backup loop.

        Logs and suppresses errors except ``MemoryError`` and
        ``RecursionError``.
        """
        while True:
            self._wake_event.clear()
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(
                    self._wake_event.wait(),
                    timeout=self._interval_seconds,
                )
            logger.debug(BACKUP_SCHEDULER_TICK)
            try:
                await self._service.create_backup(BackupTrigger.SCHEDULED)
            except MemoryError, RecursionError:
                raise
            except Exception:
                logger.error(
                    BACKUP_FAILED,
                    error="Scheduled backup failed",
                    exc_info=True,
                )
