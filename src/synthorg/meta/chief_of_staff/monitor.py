"""Async background monitor for org-level inflections.

Periodically collects a signal snapshot and compares it to the
previous snapshot using ``OrgInflectionDetector``. Detected
inflections are emitted to registered ``OrgInflectionSink``
consumers.
"""

import asyncio
import contextlib
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from synthorg.observability import get_logger
from synthorg.observability.events.chief_of_staff import (
    COS_INFLECTION_CHECK_FAILED,
    COS_INFLECTION_DETECTED,
    COS_MONITOR_STARTED,
    COS_MONITOR_STOPPED,
)

if TYPE_CHECKING:
    from synthorg.meta.chief_of_staff.inflection import OrgInflectionDetector
    from synthorg.meta.chief_of_staff.models import OrgInflection
    from synthorg.meta.chief_of_staff.protocol import OrgInflectionSink
    from synthorg.meta.models import OrgSignalSnapshot
    from synthorg.meta.signals.snapshot import SnapshotBuilder

logger = get_logger(__name__)


class OrgInflectionMonitor:
    """Background loop for org-level inflection detection.

    Collects snapshots at a configurable interval and emits
    ``OrgInflection`` events to registered sinks when metrics
    change beyond detection thresholds.

    Args:
        detector: Inflection detector instance.
        snapshot_builder: Builder for org signal snapshots.
        sinks: Consumers of detected inflections.
        check_interval_minutes: Minutes between checks.
    """

    def __init__(
        self,
        *,
        detector: OrgInflectionDetector,
        snapshot_builder: SnapshotBuilder,
        sinks: tuple[OrgInflectionSink, ...],
        check_interval_minutes: int = 15,
    ) -> None:
        if check_interval_minutes < 1:
            msg = f"check_interval_minutes must be >= 1, got {check_interval_minutes}"
            raise ValueError(msg)
        self._detector = detector
        self._builder = snapshot_builder
        self._sinks = sinks
        self._interval_s = check_interval_minutes * 60
        self._last_snapshot: OrgSignalSnapshot | None = None
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        """Start the background monitoring loop."""
        if self._task is not None:
            return
        self._task = asyncio.create_task(self._loop())
        logger.info(
            COS_MONITOR_STARTED,
            interval_minutes=self._interval_s // 60,
        )

    async def stop(self) -> None:
        """Stop the monitoring loop gracefully."""
        if self._task is None:
            return
        self._task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await self._task
        self._task = None
        self._last_snapshot = None
        logger.info(COS_MONITOR_STOPPED)

    async def _loop(self) -> None:
        """Periodic snapshot collection and inflection check."""
        while True:
            try:
                await self._tick()
            except asyncio.CancelledError:
                raise
            except MemoryError, RecursionError:
                raise
            except Exception:
                logger.exception(COS_INFLECTION_CHECK_FAILED)
            await asyncio.sleep(self._interval_s)

    async def _tick(self) -> None:
        """Single monitoring tick."""
        now = datetime.now(UTC)
        since = now - timedelta(seconds=self._interval_s)
        current = await self._builder.build(since=since, until=now)
        if self._last_snapshot is None:
            self._last_snapshot = current
            return
        inflections = await self._detector.detect(
            previous=self._last_snapshot,
            current=current,
        )
        self._last_snapshot = current
        for inflection in inflections:
            logger.info(
                COS_INFLECTION_DETECTED,
                metric=inflection.metric_name,
                severity=inflection.severity.value,
                old_value=inflection.old_value,
                new_value=inflection.new_value,
            )
            await self._emit_to_sinks(inflection)

    async def _emit_to_sinks(self, inflection: OrgInflection) -> None:
        """Emit an inflection to all sinks in parallel."""

        async def _emit(sink: OrgInflectionSink) -> None:
            try:
                await sink.on_inflection(inflection)
            except MemoryError, RecursionError:
                raise
            except Exception:
                logger.exception(
                    COS_INFLECTION_CHECK_FAILED,
                    sink=type(sink).__name__,
                )

        async with asyncio.TaskGroup() as tg:
            for sink in self._sinks:
                tg.create_task(_emit(sink))
