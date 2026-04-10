"""Tests for InflectionTrigger."""

from unittest.mock import MagicMock

import pytest

from synthorg.engine.evolution.triggers.inflection import InflectionTrigger
from synthorg.hr.enums import TrendDirection
from synthorg.hr.performance.inflection_protocol import (
    PerformanceInflection,
)


def _make_inflection(
    agent_id: str = "agent-1",
) -> PerformanceInflection:
    return PerformanceInflection(
        agent_id=agent_id,
        metric_name="quality_score",
        window_size="7d",
        old_direction=TrendDirection.STABLE,
        new_direction=TrendDirection.DECLINING,
        slope=-0.08,
    )


class TestInflectionTrigger:
    """InflectionTrigger fires on pending inflection events."""

    @pytest.mark.unit
    async def test_no_pending_does_not_fire(self) -> None:
        trigger = InflectionTrigger()
        ctx = MagicMock()
        assert not await trigger.should_trigger(agent_id="agent-1", context=ctx)

    @pytest.mark.unit
    async def test_fires_after_emit(self) -> None:
        trigger = InflectionTrigger()
        ctx = MagicMock()

        await trigger.emit(_make_inflection())
        assert await trigger.should_trigger(agent_id="agent-1", context=ctx)

    @pytest.mark.unit
    async def test_consumes_pending_on_trigger(self) -> None:
        trigger = InflectionTrigger()
        ctx = MagicMock()

        await trigger.emit(_make_inflection())
        assert await trigger.should_trigger(agent_id="agent-1", context=ctx)
        # Second call should not fire -- pending was consumed.
        assert not await trigger.should_trigger(agent_id="agent-1", context=ctx)

    @pytest.mark.unit
    async def test_independent_per_agent(self) -> None:
        trigger = InflectionTrigger()
        ctx = MagicMock()

        await trigger.emit(_make_inflection("agent-1"))
        assert await trigger.should_trigger(agent_id="agent-1", context=ctx)
        assert not await trigger.should_trigger(agent_id="agent-2", context=ctx)

    @pytest.mark.unit
    async def test_get_pending(self) -> None:
        trigger = InflectionTrigger()
        inflection = _make_inflection()
        await trigger.emit(inflection)

        pending = await trigger.get_pending("agent-1")
        assert len(pending) == 1
        assert pending[0].metric_name == "quality_score"

    @pytest.mark.unit
    def test_name(self) -> None:
        assert InflectionTrigger().name == "inflection"
