"""Tests for composite guard."""

import pytest

from synthorg.hr.scaling.enums import ScalingActionType
from synthorg.hr.scaling.guards.composite import CompositeScalingGuard
from synthorg.hr.scaling.guards.cooldown import CooldownGuard
from synthorg.hr.scaling.guards.rate_limit import RateLimitGuard

from .conftest import make_decision


@pytest.mark.unit
class TestCompositeScalingGuard:
    """CompositeScalingGuard sequential chain behavior."""

    async def test_applies_guards_in_order(self) -> None:
        cooldown = CooldownGuard(cooldown_seconds=3600)
        rate_limit = RateLimitGuard(max_hires_per_day=1)

        # Wrap filter methods to track call order
        cooldown_filter_original = cooldown.filter
        rate_limit_filter_original = rate_limit.filter
        call_order = []

        from synthorg.hr.scaling.models import ScalingDecision

        async def cooldown_filter_wrapper(
            decisions: tuple[ScalingDecision, ...],
        ) -> tuple[ScalingDecision, ...]:
            call_order.append("cooldown")
            return await cooldown_filter_original(decisions)

        async def rate_limit_filter_wrapper(
            decisions: tuple[ScalingDecision, ...],
        ) -> tuple[ScalingDecision, ...]:
            call_order.append("rate_limit")
            return await rate_limit_filter_original(decisions)

        cooldown.filter = cooldown_filter_wrapper  # type: ignore[method-assign]
        rate_limit.filter = rate_limit_filter_wrapper  # type: ignore[method-assign]

        composite = CompositeScalingGuard(
            guards=(cooldown, rate_limit),
        )

        decision = make_decision(action_type=ScalingActionType.HIRE)
        result = await composite.filter((decision,))
        assert len(result) == 1
        assert call_order == ["cooldown", "rate_limit"], (
            f"Guards executed in order: {call_order}"
        )

    async def test_second_guard_can_filter(self) -> None:
        cooldown = CooldownGuard(cooldown_seconds=3600)
        rate_limit = RateLimitGuard(max_hires_per_day=0)
        composite = CompositeScalingGuard(
            guards=(cooldown, rate_limit),
        )

        decision = make_decision(action_type=ScalingActionType.HIRE)
        result = await composite.filter((decision,))
        # Rate limit blocks (max=0).
        assert len(result) == 0

    async def test_empty_guards_passes_through(self) -> None:
        composite = CompositeScalingGuard(guards=())
        decision = make_decision()
        result = await composite.filter((decision,))
        assert len(result) == 1

    async def test_empty_decisions(self) -> None:
        composite = CompositeScalingGuard(
            guards=(CooldownGuard(),),
        )
        result = await composite.filter(())
        assert result == ()

    async def test_name_property(self) -> None:
        composite = CompositeScalingGuard(guards=())
        assert composite.name == "composite"
