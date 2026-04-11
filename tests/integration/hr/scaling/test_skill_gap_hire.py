"""Integration: skill gap -> targeted hire proposal.

End-to-end test: missing skills detected in task requirements
produce a targeted hire proposal with the skill gap strategy.
"""

import pytest

from synthorg.hr.scaling.config import ScalingConfig, SkillGapConfig
from synthorg.hr.scaling.context import ScalingContextBuilder
from synthorg.hr.scaling.enums import ScalingActionType, ScalingStrategyName
from synthorg.hr.scaling.factory import (
    create_scaling_guards,
    create_scaling_strategies,
)
from synthorg.hr.scaling.service import ScalingService
from synthorg.hr.scaling.signals.skill import SkillSignalSource

from .conftest import AGENT_IDS


@pytest.mark.integration
class TestSkillGapHire:
    """Skill gap detection produces a targeted hire proposal."""

    async def test_missing_skills_trigger_hire(self) -> None:
        config = ScalingConfig(
            skill_gap=SkillGapConfig(enabled=True, min_missing_skills=1),
        )
        strategies = create_scaling_strategies(config)
        guard = create_scaling_guards(config)

        builder = ScalingContextBuilder(
            skill_source=SkillSignalSource(),
        )

        service = ScalingService(
            strategies=strategies,
            guard=guard,
            context_builder=builder,
            config=config,
        )

        decisions = await service.evaluate(
            agent_ids=AGENT_IDS,
            context_kwargs={
                "skill_kwargs": {
                    "agent_skills": {"agent-001": ("python",)},
                    "required_skills": ("python", "go", "react"),
                },
            },
        )

        # Skill gap should produce a HIRE decision from the SKILL_GAP strategy.
        skill_gap_hires = [
            d
            for d in decisions
            if d.action_type == ScalingActionType.HIRE
            and d.source_strategy == ScalingStrategyName.SKILL_GAP
        ]
        assert len(skill_gap_hires) >= 1
        assert "missing skills" in skill_gap_hires[0].rationale.lower()
