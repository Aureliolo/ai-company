"""Tests for cooldown guard."""

from datetime import UTC, datetime

import pytest

from synthorg.hr.scaling.guards.cooldown import CooldownGuard

from .conftest import make_decision


@pytest.mark.unit
class TestCooldownGuard:
    """CooldownGuard per-target tracking and window expiry."""

    async def test_first_decision_passes(self) -> None:
        guard = CooldownGuard(cooldown_seconds=3600)
        decisions = (make_decision(),)
        result = await guard.filter(decisions)
        assert len(result) == 1

    async def test_second_decision_within_cooldown_dropped(self) -> None:
        guard = CooldownGuard(cooldown_seconds=3600)
        decision = make_decision()
        await guard.record_action(decision)
        result = await guard.filter((decision,))
        assert len(result) == 0

    async def test_decision_after_cooldown_passes(self) -> None:
        guard = CooldownGuard(cooldown_seconds=10)
        decision = make_decision()
        # Simulate expired cooldown.
        key = guard._make_key(decision)
        guard._last_action[key] = datetime(2020, 1, 1, tzinfo=UTC)
        result = await guard.filter((decision,))
        assert len(result) == 1

    async def test_different_targets_not_blocked(self) -> None:
        guard = CooldownGuard(cooldown_seconds=3600)
        d1 = make_decision(target_role="backend_developer")
        d2 = make_decision(target_role="frontend_developer")
        await guard.record_action(d1)
        result = await guard.filter((d2,))
        assert len(result) == 1

    async def test_name_property(self) -> None:
        guard = CooldownGuard()
        assert guard.name == "cooldown"
