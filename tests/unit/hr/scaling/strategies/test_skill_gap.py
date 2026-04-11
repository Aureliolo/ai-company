"""Tests for skill gap strategy."""

import pytest

from synthorg.hr.scaling.enums import ScalingActionType
from synthorg.hr.scaling.strategies.skill_gap import SkillGapStrategy

from .conftest import make_context, make_signal


@pytest.mark.unit
class TestSkillGapStrategy:
    """SkillGapStrategy decision logic."""

    async def test_disabled_returns_empty(self) -> None:
        strategy = SkillGapStrategy(enabled=False)
        ctx = make_context(
            skill_signals=(
                make_signal(name="missing_skill_count", value=3.0, source="skill"),
                make_signal(name="coverage_ratio", value=0.5, source="skill"),
            ),
        )
        decisions = await strategy.evaluate(ctx)
        assert len(decisions) == 0

    async def test_enabled_with_gaps(self) -> None:
        strategy = SkillGapStrategy(enabled=True)
        ctx = make_context(
            skill_signals=(
                make_signal(name="missing_skill_count", value=2.0, source="skill"),
                make_signal(name="coverage_ratio", value=0.5, source="skill"),
            ),
        )
        decisions = await strategy.evaluate(ctx)
        assert len(decisions) == 1
        assert decisions[0].action_type == ScalingActionType.HIRE
        assert "2 missing skills" in decisions[0].rationale

    async def test_no_gaps_returns_empty(self) -> None:
        strategy = SkillGapStrategy(enabled=True)
        ctx = make_context(
            skill_signals=(
                make_signal(name="missing_skill_count", value=0.0, source="skill"),
                make_signal(name="coverage_ratio", value=1.0, source="skill"),
            ),
        )
        decisions = await strategy.evaluate(ctx)
        assert len(decisions) == 0

    async def test_below_min_missing_returns_empty(self) -> None:
        strategy = SkillGapStrategy(enabled=True, min_missing_skills=3)
        ctx = make_context(
            skill_signals=(
                make_signal(name="missing_skill_count", value=2.0, source="skill"),
            ),
        )
        decisions = await strategy.evaluate(ctx)
        assert len(decisions) == 0

    async def test_no_signals_returns_empty(self) -> None:
        strategy = SkillGapStrategy(enabled=True)
        ctx = make_context(skill_signals=())
        decisions = await strategy.evaluate(ctx)
        assert len(decisions) == 0

    async def test_name_and_action_types(self) -> None:
        strategy = SkillGapStrategy()
        assert strategy.name == "skill_gap"
        assert ScalingActionType.HIRE in strategy.action_types
