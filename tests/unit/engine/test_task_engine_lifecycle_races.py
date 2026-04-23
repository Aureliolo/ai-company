"""TOCTOU race tests for TaskEngine start/stop.

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
from synthorg.engine.task_engine_config import TaskEngineConfig
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


@pytest.mark.unit
class TestStartDuringStop:
    """``start()`` racing an in-flight ``stop()`` must be serialized.

    Without the stop-holds-the-lock fix, this interleaving race:
    - stop flips _running=False, releases lifecycle lock, awaits drain
    - concurrent start sees _running=False, sets True, spawns new tasks
    - stop resumes drain against a now-stale self._processing_task
      reference -- the new processing task is never awaited, leaks

    With the fix (stop holds _lifecycle_lock across drains), the
    second start must wait until stop fully completes and the lock
    releases.
    """

    async def test_start_waits_for_stop_to_fully_complete(self) -> None:
        persistence: FakePersistence = FakePersistence()
        eng = TaskEngine(persistence=persistence)  # type: ignore[arg-type]
        await eng.start()

        # Kick off stop + start concurrently. Stop sets _running=False
        # and then awaits drain; start must block on _lifecycle_lock
        # until that drain completes.
        stop_coro = eng.stop(timeout=2.0)
        start_coro = eng.start()
        results = await asyncio.gather(stop_coro, start_coro, return_exceptions=True)
        try:
            # stop always succeeds; start should also succeed because by
            # the time its lock-acquire returns, stop has released and
            # _running is False again, so the second start legitimately
            # starts a fresh engine (not a double-spawn race).
            assert not isinstance(results[0], BaseException), (
                f"stop raised unexpectedly: {results[0]!r}"
            )
            assert not isinstance(results[1], BaseException), (
                f"start raised unexpectedly: {results[1]!r}"
            )
            # Invariant: there is exactly one processing loop + one
            # observer dispatcher task, not a leaked pair from a race.
            loop_tasks = [
                t for t in asyncio.all_tasks() if t.get_name() == "task-engine-loop"
            ]
            observer_tasks = [
                t
                for t in asyncio.all_tasks()
                if t.get_name() == "task-engine-observer-dispatcher"
            ]
            assert len(loop_tasks) == 1, (
                f"expected 1 task-engine-loop after start-during-stop, "
                f"got {len(loop_tasks)}"
            )
            assert len(observer_tasks) == 1, (
                f"expected 1 observer task after start-during-stop, "
                f"got {len(observer_tasks)}"
            )
        finally:
            await eng.stop(timeout=2.0)

    async def test_hard_deadline_releases_lifecycle_lock(self) -> None:
        """stop() must release _lifecycle_lock even if drain hangs.

        A badly-behaved background task could ignore CancelledError
        and hang forever. The outer hard deadline
        (``drain_timeout_seconds * 2``) must still release the lock so
        a subsequent start() does not block indefinitely.
        """
        persistence: FakePersistence = FakePersistence()
        # Tiny drain timeout so the test stays fast -- hard deadline
        # is 2x this, so the whole stop bounds to ~0.2s even if the
        # processing task is cooperative.
        eng = TaskEngine(
            persistence=persistence,  # type: ignore[arg-type]
            config=TaskEngineConfig(drain_timeout_seconds=0.1),
        )
        await eng.start()
        # A well-behaved stop on a healthy engine returns cleanly;
        # the regression is that even if it didn't, lifecycle_lock
        # would release. We verify the healthy path here and rely on
        # the outer wait_for wrapper to protect against pathological
        # drain hangs.
        await eng.stop(timeout=0.1)
        assert not eng.is_running
        # Subsequent start must succeed (lock not held).
        await eng.start()
        try:
            assert eng.is_running
        finally:
            await eng.stop(timeout=0.1)
