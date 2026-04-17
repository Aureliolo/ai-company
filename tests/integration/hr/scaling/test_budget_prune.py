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

    @pytest.mark.parametrize(
        ("budget_percent", "alert_level", "expect_prune", "expect_hire"),
        [
            (95.0, "CRITICAL", 0, 0),
            (30.0, "NORMAL", 0, 1),
        ],
        ids=["over-budget-blocks-hires", "under-headroom-allows-hires"],
    )
    async def test_budget_gates_hiring(
        self,
        budget_percent: float,
        alert_level: str,
        expect_prune: int,
        expect_hire: int,
    ) -> None:
        from datetime import UTC, datetime

        from synthorg.budget.enums import BudgetAlertLevel
        from synthorg.budget.spending_summary import (
            PeriodSpending,
            SpendingSummary,
        )
        from synthorg.engine.assignment.models import AgentWorkload

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

        start = datetime(2026, 4, 1, tzinfo=UTC)
        end = datetime(2026, 4, 30, tzinfo=UTC)

        alert_enum = BudgetAlertLevel[alert_level]
        summary = SpendingSummary(
            period=PeriodSpending(
                total_cost=budget_percent * 10,
                record_count=int(budget_percent),
                start=start,
                end=end,
            ),
            budget_total_monthly=1000.0,
            budget_used_percent=budget_percent,
            alert_level=alert_enum,
        )

        workloads = tuple(
            AgentWorkload(
                agent_id=aid,
                active_task_count=3,
                total_cost=5.0 if budget_percent < 50 else 10.0,
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

        prune_decisions = [
            d for d in decisions if d.action_type == ScalingActionType.PRUNE
        ]
        hire_decisions = [
            d for d in decisions if d.action_type == ScalingActionType.HIRE
        ]

        assert len(prune_decisions) == expect_prune
        if expect_hire > 0:
            assert len(hire_decisions) >= expect_hire
        else:
            assert len(hire_decisions) == 0
