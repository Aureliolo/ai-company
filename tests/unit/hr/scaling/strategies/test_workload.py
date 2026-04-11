"""Tests for workload auto-scale strategy."""

import pytest

from synthorg.hr.scaling.enums import ScalingActionType
from synthorg.hr.scaling.strategies.workload import WorkloadAutoScaleStrategy

from .conftest import make_context, make_signal


@pytest.mark.unit
class TestWorkloadAutoScaleStrategy:
    """WorkloadAutoScaleStrategy decision logic."""

    async def test_hire_when_above_threshold(self) -> None:
        strategy = WorkloadAutoScaleStrategy(hire_threshold=0.85)
        ctx = make_context(
            workload_signals=(make_signal(name="avg_utilization", value=0.90),),
        )
        decisions = await strategy.evaluate(ctx)
        assert len(decisions) == 1
        assert decisions[0].action_type == ScalingActionType.HIRE
        assert decisions[0].target_role is not None

    async def test_prune_when_below_threshold(self) -> None:
        strategy = WorkloadAutoScaleStrategy(prune_threshold=0.30)
        ctx = make_context(
            agent_ids=("agent-001", "agent-002", "agent-003"),
            workload_signals=(make_signal(name="avg_utilization", value=0.10),),
        )
        decisions = await strategy.evaluate(ctx)
        assert len(decisions) == 1
        assert decisions[0].action_type == ScalingActionType.PRUNE
        assert decisions[0].target_agent_id is not None

    async def test_no_action_in_normal_range(self) -> None:
        strategy = WorkloadAutoScaleStrategy(
            hire_threshold=0.85,
            prune_threshold=0.30,
        )
        ctx = make_context(
            workload_signals=(make_signal(name="avg_utilization", value=0.60),),
        )
        decisions = await strategy.evaluate(ctx)
        assert len(decisions) == 0

    async def test_no_prune_with_single_agent(self) -> None:
        strategy = WorkloadAutoScaleStrategy(prune_threshold=0.30)
        ctx = make_context(
            active_agent_count=1,
            agent_ids=("agent-001",),
            workload_signals=(make_signal(name="avg_utilization", value=0.10),),
        )
        decisions = await strategy.evaluate(ctx)
        assert len(decisions) == 0

    async def test_no_signals_returns_empty(self) -> None:
        strategy = WorkloadAutoScaleStrategy()
        ctx = make_context(workload_signals=())
        decisions = await strategy.evaluate(ctx)
        assert len(decisions) == 0

    async def test_confidence_scales_with_distance(self) -> None:
        strategy = WorkloadAutoScaleStrategy(hire_threshold=0.85)
        ctx_high = make_context(
            workload_signals=(make_signal(name="avg_utilization", value=0.99),),
        )
        ctx_low = make_context(
            workload_signals=(make_signal(name="avg_utilization", value=0.86),),
        )
        high_decisions = await strategy.evaluate(ctx_high)
        low_decisions = await strategy.evaluate(ctx_low)
        assert high_decisions[0].confidence > low_decisions[0].confidence

    async def test_name_property(self) -> None:
        strategy = WorkloadAutoScaleStrategy()
        assert strategy.name == "workload"

    async def test_action_types(self) -> None:
        strategy = WorkloadAutoScaleStrategy()
        assert ScalingActionType.HIRE in strategy.action_types
        assert ScalingActionType.PRUNE in strategy.action_types
