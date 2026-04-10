"""Tests for CompositeTrigger."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from synthorg.engine.evolution.triggers.composite import CompositeTrigger


def _make_trigger(*, fires: bool) -> AsyncMock:
    trigger = AsyncMock()
    trigger.name = "mock_trigger"
    trigger.should_trigger = AsyncMock(return_value=fires)
    return trigger


class TestCompositeTrigger:
    """CompositeTrigger OR-combines sub-triggers."""

    @pytest.mark.unit
    async def test_fires_if_any_fires(self) -> None:
        t1 = _make_trigger(fires=False)
        t2 = _make_trigger(fires=True)
        composite = CompositeTrigger(triggers=(t1, t2))

        ctx = MagicMock()
        assert await composite.should_trigger(agent_id="agent-1", context=ctx)

    @pytest.mark.unit
    async def test_does_not_fire_if_none_fire(self) -> None:
        t1 = _make_trigger(fires=False)
        t2 = _make_trigger(fires=False)
        composite = CompositeTrigger(triggers=(t1, t2))

        ctx = MagicMock()
        assert not await composite.should_trigger(agent_id="agent-1", context=ctx)

    @pytest.mark.unit
    async def test_all_triggers_evaluated(self) -> None:
        """No short-circuit -- all triggers run."""
        t1 = _make_trigger(fires=True)
        t2 = _make_trigger(fires=False)
        composite = CompositeTrigger(triggers=(t1, t2))

        ctx = MagicMock()
        await composite.should_trigger(agent_id="agent-1", context=ctx)
        t1.should_trigger.assert_called_once()
        t2.should_trigger.assert_called_once()

    @pytest.mark.unit
    def test_empty_triggers_rejected(self) -> None:
        with pytest.raises(
            ValueError,
            match="at least one sub-trigger",
        ):
            CompositeTrigger(triggers=())

    @pytest.mark.unit
    def test_name_includes_sub_triggers(self) -> None:
        t1 = _make_trigger(fires=True)
        t1.name = "batched"
        t2 = _make_trigger(fires=True)
        t2.name = "inflection"
        composite = CompositeTrigger(triggers=(t1, t2))
        assert composite.name == "composite(batched, inflection)"
