"""TOCTOU race tests for TaskEngine start/stop (issue #1534).

The un-synchronized ``start()`` at ``engine/task_engine.py:125`` did
not acquire ``_lifecycle_lock`` even though ``stop()`` did. Two paths
can race:

1. Two concurrent ``start()`` calls both observe ``_running=False``
   and both create duplicate ``_processing_task`` / ``_observer_task``
   instances, leaking the first set.
2. A concurrent ``start()`` during ``stop()``'s drain: stop flips
   ``_running=False`` under the lock, releases, then starts awaiting
   the drain -- but the racing ``start()`` now sees ``_running=False``
   and spawns a *new* processing task, which stop never drains.

The fix holds ``_lifecycle_lock`` across the full start body and the
full stop body (including drains) so the two lifecycle transitions
are mutually exclusive.
"""

import asyncio

import pytest

from synthorg.engine.task_engine import TaskEngine
from tests.unit.engine.task_engine_helpers import FakePersistence


@pytest.mark.unit
class TestConcurrentStart:
    """Concurrent ``start()`` calls must be serialized via ``_lifecycle_lock``."""

    async def test_concurrent_start_spawns_single_task_set(self) -> None:
        """Exactly one ``start()`` wins; the loser raises ``RuntimeError``.

        Invariants at the end of the gather:

        - exactly one success + one ``RuntimeError``
        - exactly one ``task-engine-loop`` task exists on the event loop
        - exactly one ``task-engine-observer-dispatcher`` task exists
        """
        persistence: FakePersistence = FakePersistence()
        eng = TaskEngine(persistence=persistence)  # type: ignore[arg-type]

        results = await asyncio.gather(
            eng.start(),
            eng.start(),
            return_exceptions=True,
        )
        try:
            successes = [r for r in results if not isinstance(r, BaseException)]
            failures = [r for r in results if isinstance(r, RuntimeError)]
            assert len(successes) == 1, f"expected one success, got {results!r}"
            assert len(failures) == 1, f"expected one RuntimeError, got {results!r}"

            loop_tasks = [
                t for t in asyncio.all_tasks() if t.get_name() == "task-engine-loop"
            ]
            assert len(loop_tasks) == 1, (
                f"expected 1 task-engine-loop, got {len(loop_tasks)}"
            )
            observer_tasks = [
                t
                for t in asyncio.all_tasks()
                if t.get_name() == "task-engine-observer-dispatcher"
            ]
            assert len(observer_tasks) == 1, (
                f"expected 1 observer task, got {len(observer_tasks)}"
            )
        finally:
            await eng.stop(timeout=2.0)
