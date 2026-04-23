"""TOCTOU race tests for MeetingScheduler.start.

``MeetingScheduler.start()`` at ``communication/meeting/scheduler.py``
(pre-fix, lines 109-148) performs an unsynchronized ``_running``
check-and-set and then spawns a periodic task per scheduled meeting
type. Two concurrent ``start()`` calls both passing the check would
double-spawn every periodic task. The fix wraps the body in a
dedicated ``_lifecycle_lock`` so exactly one caller wins.
"""

import asyncio
from unittest.mock import MagicMock

import pytest

from synthorg.communication.config import MeetingsConfig, MeetingTypeConfig
from synthorg.communication.meeting.errors import SchedulerAlreadyRunningError
from synthorg.communication.meeting.frequency import MeetingFrequency
from synthorg.communication.meeting.scheduler import MeetingScheduler


def _build_config() -> MeetingsConfig:
    """Build a MeetingsConfig with two periodic meeting types.

    A single scheduled type is enough to check the race, but two
    periodic types make the duplicate-task count easier to read.
    """
    return MeetingsConfig(
        enabled=True,
        types=(
            MeetingTypeConfig(
                name="daily_standup",
                frequency=MeetingFrequency.DAILY,
                participants=("alice", "bob"),
            ),
            MeetingTypeConfig(
                name="weekly_retro",
                frequency=MeetingFrequency.WEEKLY,
                participants=("alice", "bob"),
            ),
        ),
    )


@pytest.mark.unit
class TestConcurrentStart:
    """Concurrent ``start()`` calls must yield exactly one success."""

    async def test_concurrent_start_spawns_one_task_per_type(self) -> None:
        """Invariants at the end of ``asyncio.gather(start(), start())``:

        - exactly one success + one ``SchedulerAlreadyRunningError``
        - ``scheduler._tasks`` has exactly ``len(scheduled_types)`` tasks
          (not 2x)
        """
        config = _build_config()
        scheduler = MeetingScheduler(
            config=config,
            orchestrator=MagicMock(),
            participant_resolver=MagicMock(),
        )

        results = await asyncio.gather(
            scheduler.start(),
            scheduler.start(),
            return_exceptions=True,
        )
        try:
            successes = [r for r in results if not isinstance(r, BaseException)]
            failures = [
                r for r in results if isinstance(r, SchedulerAlreadyRunningError)
            ]
            assert len(successes) == 1, f"expected one success, got {results!r}"
            assert len(failures) == 1, (
                f"expected one SchedulerAlreadyRunningError, got {results!r}"
            )
            scheduled_types = scheduler.get_scheduled_types()
            assert len(scheduler._tasks) == len(scheduled_types), (
                f"expected {len(scheduled_types)} tasks, got {len(scheduler._tasks)}"
            )
        finally:
            await scheduler.stop()
