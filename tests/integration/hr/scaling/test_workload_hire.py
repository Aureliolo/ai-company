"""Integration: workload spike -> hire proposal -> guard chain.

End-to-end test: high utilization triggers a hire decision that
passes through the full guard chain.
"""

import pytest

from synthorg.hr.scaling.config import ScalingConfig
from synthorg.hr.scaling.context import ScalingContextBuilder
from synthorg.hr.scaling.enums import ScalingActionType
from synthorg.hr.scaling.factory import (
    create_scaling_guards,
    create_scaling_strategies,
)
from synthorg.hr.scaling.service import ScalingService
from synthorg.hr.scaling.signals.workload import WorkloadSignalSource

from .conftest import AGENT_IDS


@pytest.mark.integration
class TestWorkloadHire:
    """Workload spike produces a hire decision through the full pipeline."""

    async def test_high_utilization_produces_hire(self) -> None:
        config = ScalingConfig()
        strategies = create_scaling_strategies(config)
        guard = create_scaling_guards(config)

        builder = ScalingContextBuilder(
            workload_source=WorkloadSignalSource(max_concurrent_tasks=3),
        )

        service = ScalingService(
            strategies=strategies,
            guard=guard,
            context_builder=builder,
            config=config,
        )

        # Build context with high utilization via kwargs.
        from synthorg.engine.assignment.models import AgentWorkload

        workloads = tuple(
            AgentWorkload(
                agent_id=aid,
                active_task_count=3,  # 100% utilization
                total_cost_usd=10.0,
            )
            for aid in AGENT_IDS
        )

        decisions = await service.evaluate(
            agent_ids=AGENT_IDS,
            context_kwargs={"workload_kwargs": {"workloads": workloads}},
        )

        # Should have at least one HIRE decision from workload strategy.
        hire_decisions = [
            d for d in decisions if d.action_type == ScalingActionType.HIRE
        ]
        assert len(hire_decisions) >= 1
        assert hire_decisions[0].target_role is not None
        assert hire_decisions[0].confidence > 0

    async def test_normal_utilization_produces_no_hire(self) -> None:
        config = ScalingConfig()
        strategies = create_scaling_strategies(config)
        guard = create_scaling_guards(config)
        builder = ScalingContextBuilder(
            workload_source=WorkloadSignalSource(max_concurrent_tasks=3),
        )

        service = ScalingService(
            strategies=strategies,
            guard=guard,
            context_builder=builder,
            config=config,
        )

        from synthorg.engine.assignment.models import AgentWorkload

        workloads = tuple(
            AgentWorkload(
                agent_id=aid,
                active_task_count=1,  # 33% utilization
                total_cost_usd=5.0,
            )
            for aid in AGENT_IDS
        )

        decisions = await service.evaluate(
            agent_ids=AGENT_IDS,
            context_kwargs={"workload_kwargs": {"workloads": workloads}},
        )

        hire_decisions = [
            d for d in decisions if d.action_type == ScalingActionType.HIRE
        ]
        assert len(hire_decisions) == 0
