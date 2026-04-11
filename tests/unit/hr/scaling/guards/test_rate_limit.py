"""Tests for rate limit guard."""

import pytest

from synthorg.hr.scaling.enums import ScalingActionType
from synthorg.hr.scaling.guards.rate_limit import RateLimitGuard

from .conftest import make_decision


@pytest.mark.unit
class TestRateLimitGuard:
    """RateLimitGuard daily cap enforcement."""

    async def test_first_decision_passes(self) -> None:
        guard = RateLimitGuard(max_hires_per_day=3)
        decisions = (make_decision(action_type=ScalingActionType.HIRE),)
        result = await guard.filter(decisions)
        assert len(result) == 1

    async def test_exceeding_limit_drops_decisions(self) -> None:
        guard = RateLimitGuard(max_hires_per_day=2)
        decision = make_decision(action_type=ScalingActionType.HIRE)

        # Record 2 previous hires.
        await guard.record_action(decision)
        await guard.record_action(decision)

        result = await guard.filter((decision,))
        assert len(result) == 0

    async def test_different_action_types_tracked_separately(
        self,
    ) -> None:
        guard = RateLimitGuard(max_hires_per_day=1, max_prunes_per_day=1)
        hire = make_decision(action_type=ScalingActionType.HIRE)
        prune = make_decision(
            action_type=ScalingActionType.PRUNE,
            target_agent_id="agent-001",
            target_role=None,
        )

        await guard.record_action(hire)
        # Hire limit reached, but prune still allowed.
        result = await guard.filter((prune,))
        assert len(result) == 1

    async def test_noop_and_hold_not_rate_limited(self) -> None:
        guard = RateLimitGuard(max_hires_per_day=0, max_prunes_per_day=0)
        noop = make_decision(
            action_type=ScalingActionType.NO_OP,
            target_role=None,
        )
        hold = make_decision(
            action_type=ScalingActionType.HOLD,
            target_role=None,
        )
        result = await guard.filter((noop, hold))
        assert len(result) == 2

    async def test_name_property(self) -> None:
        guard = RateLimitGuard()
        assert guard.name == "rate_limit"
