"""TOCTOU race tests for SettingsChangeDispatcher (issue #1534).

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
