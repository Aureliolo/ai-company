"""Integration: complete scaling cycle.

End-to-end test: multiple strategies fire, conflict resolution
picks winners, guards filter, decisions are tracked.
"""

import pytest

from synthorg.hr.scaling.config import (
    BudgetCapConfig,
    ScalingConfig,
    SkillGapConfig,
)
from synthorg.hr.scaling.context import ScalingContextBuilder
from synthorg.hr.scaling.enums import ScalingStrategyName
from synthorg.hr.scaling.factory import (
    create_scaling_guards,
    create_scaling_strategies,
)
from synthorg.hr.scaling.service import ScalingService
from synthorg.hr.scaling.signals.budget import BudgetSignalSource
from synthorg.hr.scaling.signals.skill import SkillSignalSource
from synthorg.hr.scaling.signals.workload import WorkloadSignalSource

from .conftest import AGENT_IDS


@pytest.mark.integration
class TestFullCycle:
    """Complete scaling evaluation cycle with multiple strategies."""

    async def test_multi_strategy_cycle_with_history(self) -> None:
        """Multiple strategies produce decisions, history is tracked."""
        config = ScalingConfig(
            skill_gap=SkillGapConfig(enabled=True),
            budget_cap=BudgetCapConfig(enabled=False),
        )
        strategies = create_scaling_strategies(config)
        guard = create_scaling_guards(config)

        builder = ScalingContextBuilder(
            workload_source=WorkloadSignalSource(max_concurrent_tasks=3),
            budget_source=BudgetSignalSource(),
            skill_source=SkillSignalSource(),
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
                active_task_count=3,
                total_cost=10.0,
            )
            for aid in AGENT_IDS
        )

        decisions = await service.evaluate(
            agent_ids=AGENT_IDS,
            context_kwargs={
                "workload_kwargs": {"workloads": workloads},
                "skill_kwargs": {
                    "agent_skills": {"agent-001": ("python",)},
                    "required_skills": ("python", "go", "react"),
                },
            },
        )

        # Should have decisions from workload and skill gap strategies.
        assert len(decisions) >= 1

        # Both workload and skill_gap must fire for this scenario.
        expected = {
            ScalingStrategyName.WORKLOAD,
            ScalingStrategyName.SKILL_GAP,
        }
        strategy_sources = {d.source_strategy for d in decisions}
        assert expected <= strategy_sources, (
            f"Expected {expected} to be subset of {strategy_sources}"
        )

        # History should be tracked.
        recent = service.get_recent_decisions()
        assert len(recent) == len(decisions)

    async def test_disabled_service_returns_empty(self) -> None:
        """Disabled service produces no decisions."""
        config = ScalingConfig(enabled=False)
        strategies = create_scaling_strategies(config)
        guard = create_scaling_guards(config)
        builder = ScalingContextBuilder()

        service = ScalingService(
            strategies=strategies,
            guard=guard,
            context_builder=builder,
            config=config,
        )

        decisions = await service.evaluate(agent_ids=AGENT_IDS)
        assert len(decisions) == 0

    async def test_empty_agents_returns_empty(self) -> None:
        """No agents produces no hire/prune decisions."""
        config = ScalingConfig()
        strategies = create_scaling_strategies(config)
        guard = create_scaling_guards(config)
        builder = ScalingContextBuilder(
            workload_source=WorkloadSignalSource(),
        )

        service = ScalingService(
            strategies=strategies,
            guard=guard,
            context_builder=builder,
            config=config,
        )

        decisions = await service.evaluate(agent_ids=())
        # No agents means no workload, no prune targets.
        assert len(decisions) == 0
