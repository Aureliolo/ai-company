"""Integration: budget overrun -> prune + block hires.

End-to-end test: budget cap strategy prunes when over safety margin
and blocks hires from lower-priority strategies.
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
from synthorg.hr.scaling.signals.budget import BudgetSignalSource
from synthorg.hr.scaling.signals.workload import WorkloadSignalSource

from .conftest import AGENT_IDS


@pytest.mark.integration
class TestBudgetPrune:
    """Budget pressure triggers pruning and blocks hiring."""

    async def test_over_budget_prunes_and_blocks_hires(self) -> None:
        """When budget exceeds safety margin, prune fires and hires blocked."""
        config = ScalingConfig()
        strategies = create_scaling_strategies(config)
        guard = create_scaling_guards(config)

        builder = ScalingContextBuilder(
            workload_source=WorkloadSignalSource(max_concurrent_tasks=3),
            budget_source=BudgetSignalSource(),
        )

        service = ScalingService(
            strategies=strategies,
            guard=guard,
            context_builder=builder,
            config=config,
        )

        from datetime import UTC, datetime

        from synthorg.budget.enums import BudgetAlertLevel
        from synthorg.budget.spending_summary import (
            PeriodSpending,
            SpendingSummary,
        )
        from synthorg.engine.assignment.models import AgentWorkload

        start = datetime(2026, 4, 1, tzinfo=UTC)
        end = datetime(2026, 4, 30, tzinfo=UTC)

        summary = SpendingSummary(
            period=PeriodSpending(
                total_cost_usd=900.0,
                record_count=100,
                start=start,
                end=end,
            ),
            budget_total_monthly=1000.0,
            budget_used_percent=95.0,  # Over safety margin (90%)
            alert_level=BudgetAlertLevel.CRITICAL,
        )

        # Also set high utilization to trigger workload hire.
        workloads = tuple(
            AgentWorkload(
                agent_id=aid,
                active_task_count=3,
                total_cost_usd=10.0,
            )
            for aid in AGENT_IDS
        )

        decisions = await service.evaluate(
            agent_ids=AGENT_IDS,
            context_kwargs={
                "workload_kwargs": {"workloads": workloads},
                "budget_kwargs": {"summary": summary},
            },
        )

        # Budget cap should produce PRUNE (highest priority).
        prune_decisions = [
            d for d in decisions if d.action_type == ScalingActionType.PRUNE
        ]
        assert len(prune_decisions) >= 1

        # Workload HIRE should be blocked by budget HOLD.
        hire_decisions = [
            d for d in decisions if d.action_type == ScalingActionType.HIRE
        ]
        assert len(hire_decisions) == 0

    async def test_under_headroom_allows_hires(self) -> None:
        """When budget is under headroom, hires pass through."""
        config = ScalingConfig()
        strategies = create_scaling_strategies(config)
        guard = create_scaling_guards(config)

        builder = ScalingContextBuilder(
            workload_source=WorkloadSignalSource(max_concurrent_tasks=3),
            budget_source=BudgetSignalSource(),
        )

        service = ScalingService(
            strategies=strategies,
            guard=guard,
            context_builder=builder,
            config=config,
        )

        from datetime import UTC, datetime

        from synthorg.budget.enums import BudgetAlertLevel
        from synthorg.budget.spending_summary import (
            PeriodSpending,
            SpendingSummary,
        )
        from synthorg.engine.assignment.models import AgentWorkload

        start = datetime(2026, 4, 1, tzinfo=UTC)
        end = datetime(2026, 4, 30, tzinfo=UTC)

        summary = SpendingSummary(
            period=PeriodSpending(
                total_cost_usd=300.0,
                record_count=30,
                start=start,
                end=end,
            ),
            budget_total_monthly=1000.0,
            budget_used_percent=30.0,  # Under headroom (60%)
            alert_level=BudgetAlertLevel.NORMAL,
        )

        workloads = tuple(
            AgentWorkload(
                agent_id=aid,
                active_task_count=3,
                total_cost_usd=5.0,
            )
            for aid in AGENT_IDS
        )

        decisions = await service.evaluate(
            agent_ids=AGENT_IDS,
            context_kwargs={
                "workload_kwargs": {"workloads": workloads},
                "budget_kwargs": {"summary": summary},
            },
        )

        hire_decisions = [
            d for d in decisions if d.action_type == ScalingActionType.HIRE
        ]
        assert len(hire_decisions) >= 1
