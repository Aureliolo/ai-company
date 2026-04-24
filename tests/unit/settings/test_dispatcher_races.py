"""TOCTOU race tests for SettingsChangeDispatcher.

Unlike the bridge and engine, settings/dispatcher.py has a real
``await`` between the ``_running`` check and the final ``_running =
True`` assignment: ``_ensure_channel()`` and ``_bus.subscribe()`` both
yield the event loop. Two concurrent ``start()`` calls can both pass
the initial ``if self._running:`` guard, both subscribe to
``#settings``, and both spawn a poll-loop task with duplicate
subscribers attached.

The fix wraps the whole start body in ``_lifecycle_lock`` so exactly
one caller wins.
"""

import asyncio

import pytest

from synthorg.communication.bus.memory import InMemoryMessageBus
from synthorg.communication.config import MessageBusConfig
from synthorg.settings.dispatcher import SettingsChangeDispatcher


@pytest.mark.unit
class TestConcurrentStart:
    """Two concurrent ``start()`` calls must be serialized."""

    async def test_concurrent_start_yields_one_success_one_error(self) -> None:
        """Invariants after ``asyncio.gather(start(), start())``:

        - exactly one start returns successfully
        - exactly one raises ``RuntimeError``
        - at most one poll task named ``settings-dispatcher`` exists
        """
        bus = InMemoryMessageBus(config=MessageBusConfig())
        await bus.start()
        dispatcher = SettingsChangeDispatcher(bus, subscribers=())

        results = await asyncio.gather(
            dispatcher.start(),
            dispatcher.start(),
            return_exceptions=True,
        )
        try:
            successes = [r for r in results if not isinstance(r, BaseException)]
            failures = [r for r in results if isinstance(r, RuntimeError)]
            assert len(successes) == 1, f"expected one success, got {results!r}"
            assert len(failures) == 1, f"expected one RuntimeError, got {results!r}"
            # Exactly one task should be running for the dispatcher.
            running_tasks = [
                t for t in asyncio.all_tasks() if t.get_name() == "settings-dispatcher"
            ]
            assert len(running_tasks) == 1, (
                f"expected one settings-dispatcher task, got {len(running_tasks)}"
            )
        finally:
            await dispatcher.stop()
            await bus.stop()


@pytest.mark.unit
class TestStartDuringStop:
    """``start()`` racing an in-flight ``stop()`` must wait for stop."""

    async def test_start_waits_for_stop_lock_release(self) -> None:
        """A concurrent start during stop must not spawn a duplicate task.

        With `_lifecycle_lock` guarding both start and stop, the
        second start observes `_running=False` only after stop has
        fully released the lock. Invariant at gather completion:
        exactly one `settings-dispatcher` task exists (the one the
        winning start spawned).

        Deterministic ordering is enforced: we launch ``stop()`` first,
        wait for it to actually acquire ``_lifecycle_lock`` via a
        monkey-patched sentinel on the drain path, then launch
        ``start()``. A plain ``asyncio.gather(stop, start)`` does NOT
        guarantee ``stop()`` grabs the lock first; if ``start()`` runs
        first it raises "already running" and the assertion still
        passes by accident, so the test would not actually pin the
        "start-during-stop" contract it claims to verify.
        """
        bus = InMemoryMessageBus(config=MessageBusConfig())
        await bus.start()
        dispatcher = SettingsChangeDispatcher(bus, subscribers=())
        await dispatcher.start()

        # Sentinel fired from inside stop() while it holds the
        # lifecycle lock -- by the time we see it, stop() is past its
        # check-and-set and the outer start() attempt is guaranteed
        # to serialize behind the lock release.
        stop_holding_lock = asyncio.Event()

        original_stop = dispatcher.stop

        async def instrumented_stop() -> None:
            # Signal the test loop as soon as we're under the lock,
            # then yield so the test can schedule start() before the
            # drain completes. ``asyncio.sleep(0)`` forces at least
            # one pass through the event loop so the racing start()
            # has a chance to contest the lock.
            async def _signal_then_stop() -> None:
                stop_holding_lock.set()
                await asyncio.sleep(0)
                await original_stop()

            await _signal_then_stop()

        dispatcher.stop = instrumented_stop  # type: ignore[method-assign]

        stop_task = asyncio.create_task(dispatcher.stop())
        await stop_holding_lock.wait()
        start_coro = dispatcher.start()
        results = await asyncio.gather(stop_task, start_coro, return_exceptions=True)
        try:
            assert not isinstance(results[0], BaseException), (
                f"stop raised unexpectedly: {results[0]!r}"
            )
            assert not isinstance(results[1], BaseException), (
                f"start raised unexpectedly: {results[1]!r}"
            )
            running_tasks = [
                t for t in asyncio.all_tasks() if t.get_name() == "settings-dispatcher"
            ]
            assert len(running_tasks) == 1, (
                f"expected one settings-dispatcher after start-during-stop, "
                f"got {len(running_tasks)}"
            )
        finally:
            dispatcher.stop = original_stop  # type: ignore[method-assign]
            await dispatcher.stop()
            await bus.stop()
