"""Tests for scaling context builder."""

import pytest
from pydantic import ValidationError

from synthorg.core.types import NotBlankStr
from synthorg.hr.scaling.context import ScalingContextBuilder
from synthorg.hr.scaling.signals.budget import BudgetSignalSource
from synthorg.hr.scaling.signals.skill import SkillSignalSource
from synthorg.hr.scaling.signals.workload import WorkloadSignalSource

_AGENT_IDS = (NotBlankStr("a1"), NotBlankStr("a2"))


@pytest.mark.unit
class TestScalingContextBuilder:
    """ScalingContextBuilder assembly and integration."""

    @pytest.mark.parametrize(
        (
            "workload_source",
            "budget_source",
            "skill_source",
            "expected_lens",
        ),
        [
            (None, None, None, (0, 0, 0)),
            (WorkloadSignalSource(max_concurrent_tasks=3), None, None, (3, 0, 0)),
            (None, BudgetSignalSource(), None, (0, 2, 0)),
            (None, None, SkillSignalSource(), (0, 0, 2)),
            (
                WorkloadSignalSource(),
                BudgetSignalSource(),
                SkillSignalSource(),
                (3, 2, 2),
            ),
        ],
        ids=[
            "no-sources",
            "workload-source-only",
            "budget-source-only",
            "skill-source-only",
            "multiple-sources",
        ],
    )
    async def test_source_combination(
        self,
        workload_source,
        budget_source,
        skill_source,
        expected_lens,
    ) -> None:
        expected_workload_len, expected_budget_len, expected_skill_len = expected_lens
        builder = ScalingContextBuilder(
            workload_source=workload_source,
            budget_source=budget_source,
            skill_source=skill_source,
        )
        ctx = await builder.build(agent_ids=_AGENT_IDS)
        assert ctx.active_agent_count == 2
        assert ctx.agent_ids == _AGENT_IDS
        assert len(ctx.workload_signals) == expected_workload_len
        assert len(ctx.budget_signals) == expected_budget_len
        if skill_source is not None and expected_skill_len > 0:
            skill_ctx = await ScalingContextBuilder(skill_source=skill_source).build(
                agent_ids=_AGENT_IDS,
                skill_kwargs={
                    "agent_skills": {"a1": ("python",)},
                    "required_skills": ("python", "go"),
                },
            )
            assert len(skill_ctx.skill_signals) == expected_skill_len
        else:
            assert len(ctx.skill_signals) == expected_skill_len

    async def test_context_is_frozen(self) -> None:
        builder = ScalingContextBuilder()
        ctx = await builder.build(agent_ids=_AGENT_IDS)
        with pytest.raises(ValidationError):
            ctx.active_agent_count = 99  # type: ignore[misc]

    async def test_empty_agent_ids(self) -> None:
        builder = ScalingContextBuilder()
        ctx = await builder.build(agent_ids=())
        assert ctx.active_agent_count == 0
        assert ctx.agent_ids == ()
