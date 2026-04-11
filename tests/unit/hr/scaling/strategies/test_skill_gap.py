"""Tests for skill gap strategy."""

import pytest

from synthorg.hr.scaling.enums import ScalingActionType
from synthorg.hr.scaling.strategies.skill_gap import SkillGapStrategy

from .conftest import make_context, make_signal


@pytest.mark.unit
class TestSkillGapStrategy:
    """SkillGapStrategy decision logic."""

    @pytest.mark.parametrize(
        ("enabled", "min_missing_skills", "missing_count", "expected_len"),
        [
            (False, 1, 3.0, 0),
            (True, 1, 2.0, 1),
            (True, 1, 0.0, 0),
            (True, 3, 2.0, 0),
        ],
        ids=[
            "disabled-returns-empty",
            "enabled-with-gaps",
            "no-gaps-returns-empty",
            "below-min-missing-returns-empty",
        ],
    )
    async def test_strategy_evaluation(
        self,
        enabled: bool,
        min_missing_skills: int,
        missing_count: float,
        expected_len: int,
    ) -> None:
        strategy = SkillGapStrategy(
            enabled=enabled,
            min_missing_skills=min_missing_skills,
        )
        signals = (
            (
                make_signal(
                    name="missing_skill_count",
                    value=missing_count,
                    source="skill",
                ),
                make_signal(name="coverage_ratio", value=0.5, source="skill"),
            )
            if missing_count > 0.0 or expected_len > 0
            else ()
        )
        ctx = make_context(skill_signals=signals)
        decisions = await strategy.evaluate(ctx)
        assert len(decisions) == expected_len
        if expected_len > 0:
            assert decisions[0].action_type == ScalingActionType.HIRE
            assert f"{int(missing_count)} missing skills" in decisions[0].rationale

    async def test_name_and_action_types(self) -> None:
        strategy = SkillGapStrategy()
        assert strategy.name == "skill_gap"
        assert ScalingActionType.HIRE in strategy.action_types
