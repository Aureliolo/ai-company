"""Tests for BatchedTrigger."""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest

from synthorg.engine.evolution.triggers.batched import BatchedTrigger


class TestBatchedTrigger:
    """BatchedTrigger fires based on time intervals."""

    @pytest.mark.unit
    async def test_fires_on_first_call(self) -> None:
        trigger = BatchedTrigger(interval_seconds=3600)
        ctx = MagicMock()
        assert await trigger.should_trigger(agent_id="agent-1", context=ctx)

    @pytest.mark.unit
    async def test_does_not_fire_within_interval(self) -> None:
        trigger = BatchedTrigger(interval_seconds=3600)
        ctx = MagicMock()
        assert await trigger.should_trigger(agent_id="agent-1", context=ctx)
        # Immediately again -- should not fire.
        assert not await trigger.should_trigger(agent_id="agent-1", context=ctx)

    @pytest.mark.unit
    async def test_fires_after_interval(self) -> None:
        trigger = BatchedTrigger(interval_seconds=60)
        ctx = MagicMock()

        # First call fires and records time.
        assert await trigger.should_trigger(agent_id="agent-1", context=ctx)

        # Backdate the last run.
        trigger._last_run["agent-1"] = datetime.now(UTC) - timedelta(seconds=120)
        assert await trigger.should_trigger(agent_id="agent-1", context=ctx)

    @pytest.mark.unit
    async def test_independent_per_agent(self) -> None:
        trigger = BatchedTrigger(interval_seconds=3600)
        ctx = MagicMock()
        assert await trigger.should_trigger(agent_id="agent-1", context=ctx)
        # Different agent -- should still fire.
        assert await trigger.should_trigger(agent_id="agent-2", context=ctx)
        # agent-1 again within interval -- should not.
        assert not await trigger.should_trigger(agent_id="agent-1", context=ctx)

    @pytest.mark.unit
    def test_record_run(self) -> None:
        trigger = BatchedTrigger()
        trigger.record_run("agent-1")
        assert "agent-1" in trigger._last_run

    @pytest.mark.unit
    def test_name(self) -> None:
        assert BatchedTrigger().name == "batched"
