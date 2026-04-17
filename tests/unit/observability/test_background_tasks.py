"""Unit tests for BackgroundTaskRegistry."""

import asyncio
import logging
from collections.abc import MutableMapping
from typing import Any

import pytest

from synthorg.observability.background_tasks import BackgroundTaskRegistry
from synthorg.observability.events.async_task import (
    BACKGROUND_TASKS_DRAIN_TIMEOUT,
)
from synthorg.observability.events.notification import NOTIFICATION_SEND_FAILED

pytestmark = pytest.mark.unit


async def _noop() -> None:
    return None


async def _raiser(exc: BaseException) -> None:
    raise exc


async def _block_until_set(blocker: asyncio.Event) -> None:
    """Block until *blocker* is set, or the task is cancelled.

    Used as a deterministic replacement for ``asyncio.sleep`` in
    timing-sensitive tests: the caller controls exactly when the
    coroutine completes or gets cancelled, eliminating real-time
    dependencies and xdist flakiness.
    """
    await blocker.wait()


async def test_spawn_tracks_task_and_discards_on_success() -> None:
    registry = BackgroundTaskRegistry(owner="test.owner")
    task = registry.spawn(_noop(), event="test.intent")
    assert registry.active_count == 1
    await task
    await asyncio.sleep(0)
    assert registry.active_count == 0


async def test_failed_task_logs_notification_send_failed(
    captured_logs: list[MutableMapping[str, Any]],
) -> None:
    registry = BackgroundTaskRegistry(owner="test.owner")
    registry.spawn(
        _raiser(ValueError("notify failed")),
        event="test.intent",
        severity="critical",
        agent_id="agent-42",
    )
    # Allow task body + done-callback to run.
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    assert registry.active_count == 0
    failures = [
        entry for entry in captured_logs if entry["event"] == NOTIFICATION_SEND_FAILED
    ]
    assert len(failures) == 1
    entry = failures[0]
    assert entry["log_level"] == "error"
    assert entry["owner"] == "test.owner"
    assert entry["intent_event"] == "test.intent"
    assert entry["severity"] == "critical"
    assert entry["agent_id"] == "agent-42"
    assert entry["error_type"] == "ValueError"


async def test_cancelled_task_does_not_log_failure(
    captured_logs: list[MutableMapping[str, Any]],
) -> None:
    registry = BackgroundTaskRegistry(owner="test.owner")
    blocker = asyncio.Event()
    task = registry.spawn(_block_until_set(blocker), event="test.intent")
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    await asyncio.sleep(0)
    assert registry.active_count == 0
    failures = [
        entry for entry in captured_logs if entry["event"] == NOTIFICATION_SEND_FAILED
    ]
    assert not failures


async def test_drain_waits_for_pending_tasks() -> None:
    registry = BackgroundTaskRegistry(owner="test.owner")
    blocker = asyncio.Event()
    registry.spawn(_block_until_set(blocker), event="test.intent")
    registry.spawn(_block_until_set(blocker), event="test.intent")
    assert registry.active_count == 2
    # Release both blockers so drain has something to wait on
    # (rather than a timing-dependent 50ms sleep).
    blocker.set()
    await registry.drain(timeout_sec=1.0)
    assert registry.active_count == 0


async def test_drain_cancels_on_timeout(
    captured_logs: list[MutableMapping[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry = BackgroundTaskRegistry(owner="test.owner")
    blocker = asyncio.Event()  # Never set -- task is stuck forever.
    task = registry.spawn(_block_until_set(blocker), event="test.intent")

    # Drive the timeout branch deterministically: stub
    # ``asyncio.wait`` so both drain phases return "all pending"
    # without a real 50ms wall-clock wait. This keeps the test
    # off the CI scheduler's timing and rules out xdist jitter.
    original_wait = asyncio.wait

    async def _immediate_wait(
        tasks: set[asyncio.Task[Any]],
        *,
        timeout: float | None = None,  # noqa: ASYNC109 - mirrors asyncio.wait
        **_: Any,
    ) -> tuple[set[asyncio.Task[Any]], set[asyncio.Task[Any]]]:
        del timeout
        return (set(), set(tasks))

    monkeypatch.setattr("asyncio.wait", _immediate_wait)
    try:
        await registry.drain(timeout_sec=0.05)
    finally:
        monkeypatch.setattr("asyncio.wait", original_wait)

    # Allow the cancellation to settle.
    await asyncio.sleep(0)
    assert task.cancelled() or task.done()
    warn_entries = [
        entry
        for entry in captured_logs
        if entry["event"] == BACKGROUND_TASKS_DRAIN_TIMEOUT
    ]
    assert len(warn_entries) == 1
    entry = warn_entries[0]
    assert entry["log_level"] == "warning"
    assert entry["owner"] == "test.owner"
    assert entry["pending_count"] == 1
    assert entry["timeout_sec"] == 0.05


async def test_drain_is_noop_when_no_tasks() -> None:
    registry = BackgroundTaskRegistry(owner="test.owner")
    await asyncio.wait_for(registry.drain(timeout_sec=0.01), timeout=0.2)


async def test_no_task_exception_warning_on_failed_task(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """asyncio must not emit 'Task exception was never retrieved'.

    A bare ``asyncio.create_task`` whose exception is never observed
    triggers that warning. Our registry's done-callback calls
    ``task.exception()`` before discarding the reference, so asyncio
    considers the exception retrieved and keeps quiet.
    """
    registry = BackgroundTaskRegistry(owner="test.owner")
    caplog.set_level(logging.WARNING)
    registry.spawn(_raiser(RuntimeError("boom")), event="test.intent")
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    assert not any(
        "Task exception was never retrieved" in (r.getMessage() or "")
        for r in caplog.records
    )
