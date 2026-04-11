"""Tests for scaling context builder."""

import pytest

from synthorg.core.types import NotBlankStr
from synthorg.hr.scaling.context import ScalingContextBuilder
from synthorg.hr.scaling.signals.budget import BudgetSignalSource
from synthorg.hr.scaling.signals.skill import SkillSignalSource
from synthorg.hr.scaling.signals.workload import WorkloadSignalSource

_AGENT_IDS = (NotBlankStr("a1"), NotBlankStr("a2"))


@pytest.mark.unit
class TestScalingContextBuilder:
    """ScalingContextBuilder assembly and integration."""

    async def test_build_with_no_sources(self) -> None:
        builder = ScalingContextBuilder()
        ctx = await builder.build(agent_ids=_AGENT_IDS)
        assert ctx.active_agent_count == 2
        assert ctx.agent_ids == _AGENT_IDS
        assert ctx.workload_signals == ()
        assert ctx.budget_signals == ()
        assert ctx.performance_signals == ()
        assert ctx.skill_signals == ()

    async def test_build_with_workload_source(self) -> None:
        builder = ScalingContextBuilder(
            workload_source=WorkloadSignalSource(max_concurrent_tasks=3),
        )
        ctx = await builder.build(agent_ids=_AGENT_IDS)
        assert len(ctx.workload_signals) == 3  # avg, peak, queue
        assert ctx.budget_signals == ()

    async def test_build_with_budget_source(self) -> None:
        builder = ScalingContextBuilder(
            budget_source=BudgetSignalSource(),
        )
        ctx = await builder.build(agent_ids=_AGENT_IDS)
        assert len(ctx.budget_signals) == 2  # burn_rate, alert
        assert ctx.workload_signals == ()

    async def test_build_with_skill_source(self) -> None:
        builder = ScalingContextBuilder(
            skill_source=SkillSignalSource(),
        )
        ctx = await builder.build(
            agent_ids=_AGENT_IDS,
            skill_kwargs={
                "agent_skills": {"a1": ("python",)},
                "required_skills": ("python", "go"),
            },
        )
        assert len(ctx.skill_signals) == 2
        by_name = {s.name: s.value for s in ctx.skill_signals}
        assert by_name["coverage_ratio"] == 0.5

    async def test_build_with_multiple_sources(self) -> None:
        builder = ScalingContextBuilder(
            workload_source=WorkloadSignalSource(),
            budget_source=BudgetSignalSource(),
            skill_source=SkillSignalSource(),
        )
        ctx = await builder.build(agent_ids=_AGENT_IDS)
        assert len(ctx.workload_signals) == 3
        assert len(ctx.budget_signals) == 2
        assert len(ctx.skill_signals) == 2

    async def test_context_is_frozen(self) -> None:
        builder = ScalingContextBuilder()
        ctx = await builder.build(agent_ids=_AGENT_IDS)
        with pytest.raises(Exception):  # noqa: B017, PT011
            ctx.active_agent_count = 99  # type: ignore[misc]

    async def test_empty_agent_ids(self) -> None:
        builder = ScalingContextBuilder()
        ctx = await builder.build(agent_ids=())
        assert ctx.active_agent_count == 0
        assert ctx.agent_ids == ()
