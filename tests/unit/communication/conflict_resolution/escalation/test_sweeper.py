"""Tests for :class:`EscalationExpirationSweeper` (#1418)."""

import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from synthorg.communication.conflict_resolution.escalation.in_memory_store import (
    InMemoryEscalationStore,
)
from synthorg.communication.conflict_resolution.escalation.models import (
    Escalation,
    EscalationStatus,
)
from synthorg.communication.conflict_resolution.escalation.sweeper import (
    EscalationExpirationSweeper,
)
from synthorg.communication.conflict_resolution.models import (
    Conflict,
    ConflictPosition,
)
from synthorg.communication.enums import ConflictType
from synthorg.core.enums import SeniorityLevel

pytestmark = pytest.mark.unit


def _make_escalation(
    *,
    escalation_id: str,
    expires_at: datetime | None,
) -> Escalation:
    """Build a pending escalation with a configurable deadline."""
    conflict = Conflict(
        id=f"conflict-for-{escalation_id}",
        type=ConflictType.ARCHITECTURE,
        subject="Backend storage engine",
        positions=(
            ConflictPosition(
                agent_id="agent-a",
                agent_department="engineering",
                agent_level=SeniorityLevel.SENIOR,
                position="PostgreSQL",
                reasoning="Strong consistency",
                timestamp=datetime.now(UTC),
            ),
            ConflictPosition(
                agent_id="agent-b",
                agent_department="engineering",
                agent_level=SeniorityLevel.SENIOR,
                position="SQLite",
                reasoning="Simpler ops",
                timestamp=datetime.now(UTC),
            ),
        ),
        detected_at=datetime.now(UTC),
    )
    return Escalation(
        id=escalation_id,
        conflict=conflict,
        created_at=datetime.now(UTC),
        expires_at=expires_at,
    )


class TestSweeperLifecycle:
    async def test_start_is_idempotent(self) -> None:
        store = InMemoryEscalationStore()
        sweeper = EscalationExpirationSweeper(store, interval_seconds=1.0)
        try:
            await sweeper.start()
            first_task = sweeper._task
            await sweeper.start()
            second_task = sweeper._task
            assert first_task is second_task
        finally:
            await sweeper.stop()

    async def test_stop_cancels_task(self) -> None:
        store = InMemoryEscalationStore()
        sweeper = EscalationExpirationSweeper(store, interval_seconds=1.0)
        await sweeper.start()
        task = sweeper._task
        assert task is not None
        await sweeper.stop()
        assert task.done()
        assert sweeper._task is None

    async def test_stop_without_start_is_noop(self) -> None:
        store = InMemoryEscalationStore()
        sweeper = EscalationExpirationSweeper(store, interval_seconds=1.0)
        # Should not raise.
        await sweeper.stop()

    async def test_interval_below_1s_raises(self) -> None:
        store = InMemoryEscalationStore()
        with pytest.raises(ValueError, match="interval_seconds"):
            EscalationExpirationSweeper(store, interval_seconds=0.5)


class TestSweeperRunLoop:
    async def test_sweep_expires_stale_rows_on_loop_tick(self) -> None:
        """One full `start -> wait -> stop` cycle expires overdue rows."""
        store = InMemoryEscalationStore()
        past = datetime.now(UTC) - timedelta(seconds=10)
        stale = _make_escalation(escalation_id="esc-stale", expires_at=past)
        future_deadline = datetime.now(UTC) + timedelta(seconds=3600)
        live = _make_escalation(escalation_id="esc-live", expires_at=future_deadline)
        await store.create(stale)
        await store.create(live)

        sweeper = EscalationExpirationSweeper(store, interval_seconds=1.0)
        await sweeper.start()
        try:
            # Give the loop one full iteration to run.
            await asyncio.sleep(0.5)
        finally:
            await sweeper.stop()

        expired = await store.get("esc-stale")
        alive = await store.get("esc-live")
        assert expired is not None
        assert expired.status == EscalationStatus.EXPIRED
        assert alive is not None
        assert alive.status == EscalationStatus.PENDING

    async def test_sweeper_survives_store_exception(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When the store raises, the loop logs + continues to the next tick."""
        store = InMemoryEscalationStore()
        calls = {"n": 0}
        original = store.mark_expired

        async def flaky(now_iso: str) -> tuple[str, ...]:
            calls["n"] += 1
            if calls["n"] == 1:
                msg = "simulated transient failure"
                raise RuntimeError(msg)
            return await original(now_iso)

        monkeypatch.setattr(store, "mark_expired", flaky)
        sweeper = EscalationExpirationSweeper(store, interval_seconds=1.0)
        await sweeper.start()
        try:
            # Wait long enough for at least two ticks.
            await asyncio.sleep(1.5)
        finally:
            await sweeper.stop()
        # Loop survived the first exception and ran at least once more.
        assert calls["n"] >= 2

    async def test_restart_recovery_orphan_pending_gets_expired(self) -> None:
        """PENDING rows without a live awaiting coroutine get expired.

        Simulates the restart path: a resolver registered a Future, the
        process died (Future gone), the row is still PENDING with a
        past ``expires_at``.  The sweeper must reap it so the queue
        does not leak orphaned entries.
        """
        store = InMemoryEscalationStore()
        past = datetime.now(UTC) - timedelta(seconds=30)
        orphan = _make_escalation(
            escalation_id="esc-orphan",
            expires_at=past,
        )
        await store.create(orphan)
        # No registry, no Future -- only the row in the store.

        sweeper = EscalationExpirationSweeper(store, interval_seconds=1.0)
        await sweeper.start()
        try:
            await asyncio.sleep(0.5)
        finally:
            await sweeper.stop()
        row = await store.get("esc-orphan")
        assert row is not None
        assert row.status == EscalationStatus.EXPIRED
