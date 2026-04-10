"""Tests for PerTaskTrigger."""

from unittest.mock import MagicMock

import pytest

from synthorg.engine.evolution.triggers.per_task import PerTaskTrigger


class TestPerTaskTrigger:
    """PerTaskTrigger fires based on task count."""

    @pytest.mark.unit
    async def test_fires_on_first_task_default(self) -> None:
        trigger = PerTaskTrigger()
        ctx = MagicMock()
        assert await trigger.should_trigger(agent_id="agent-1", context=ctx)

    @pytest.mark.unit
    async def test_fires_every_task(self) -> None:
        trigger = PerTaskTrigger(min_tasks_since_last=1)
        ctx = MagicMock()
        for _ in range(5):
            assert await trigger.should_trigger(agent_id="agent-1", context=ctx)

    @pytest.mark.unit
    async def test_respects_min_tasks(self) -> None:
        trigger = PerTaskTrigger(min_tasks_since_last=3)
        ctx = MagicMock()
        results = [
            await trigger.should_trigger(agent_id="agent-1", context=ctx)
            for _ in range(6)
        ]
        # Should fire on task 3 and 6.
        assert results == [False, False, True, False, False, True]

    @pytest.mark.unit
    async def test_independent_per_agent(self) -> None:
        trigger = PerTaskTrigger(min_tasks_since_last=2)
        ctx = MagicMock()
        assert not await trigger.should_trigger(agent_id="agent-1", context=ctx)
        assert not await trigger.should_trigger(agent_id="agent-2", context=ctx)
        assert await trigger.should_trigger(agent_id="agent-1", context=ctx)
        # agent-2 still needs one more.
        assert await trigger.should_trigger(agent_id="agent-2", context=ctx)

    @pytest.mark.unit
    def test_name(self) -> None:
        assert PerTaskTrigger().name == "per_task"
