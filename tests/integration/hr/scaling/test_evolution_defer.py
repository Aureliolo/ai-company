"""Integration: performance pruning deferred during evolution.

End-to-end test: performance regression on an agent with active
evolution adaptations defers the prune proposal.
"""

import pytest

from synthorg.core.types import NotBlankStr
from synthorg.hr.enums import TrendDirection
from synthorg.hr.performance.models import (
    AgentPerformanceSnapshot,
    TrendResult,
    WindowMetrics,
)
from synthorg.hr.pruning.models import PruningEvaluation
from synthorg.hr.scaling.config import ScalingConfig
from synthorg.hr.scaling.context import ScalingContextBuilder
from synthorg.hr.scaling.enums import ScalingActionType
from synthorg.hr.scaling.guards.composite import CompositeScalingGuard
from synthorg.hr.scaling.guards.conflict_resolver import ConflictResolver
from synthorg.hr.scaling.service import ScalingService
from synthorg.hr.scaling.strategies.performance_pruning import (
    PerformancePruningStrategy,
)

from .conftest import AGENT_IDS, NOW


class _StubPruningPolicy:
    """Policy that marks all agents as eligible for pruning."""

    async def evaluate(
        self,
        agent_id: NotBlankStr,
        snapshot: AgentPerformanceSnapshot,
    ) -> PruningEvaluation:
        return PruningEvaluation(
            agent_id=agent_id,
            eligible=True,
            reasons=(NotBlankStr("quality below threshold"),),
            scores={"quality": 2.0},
            policy_name=NotBlankStr("stub"),
            snapshot=snapshot,
            evaluated_at=NOW,
        )


def _make_snapshot(agent_id: str) -> AgentPerformanceSnapshot:
    return AgentPerformanceSnapshot(
        agent_id=NotBlankStr(agent_id),
        computed_at=NOW,
        windows=(
            WindowMetrics(
                window_size=NotBlankStr("7d"),
                data_point_count=10,
                tasks_completed=5,
                tasks_failed=5,
                currency="EUR",
            ),
        ),
        trends=(
            TrendResult(
                metric_name=NotBlankStr("quality_score"),
                window_size=NotBlankStr("7d"),
                direction=TrendDirection.DECLINING,
                slope=-0.5,
                data_point_count=10,
            ),
        ),
    )


@pytest.mark.integration
class TestEvolutionDefer:
    """Performance pruning deferred when evolution is active."""

    async def test_defers_when_evolution_adapting(self) -> None:
        """Agent under active evolution is not pruned."""

        async def _always_adapting(agent_id: str) -> bool:
            return True

        strategy = PerformancePruningStrategy(
            policy=_StubPruningPolicy(),
            evolution_checker=_always_adapting,
            defer_during_evolution=True,
        )

        guard = CompositeScalingGuard(
            guards=(ConflictResolver(),),
        )

        service = ScalingService(
            strategies=(strategy,),
            guard=guard,
            context_builder=ScalingContextBuilder(),
            config=ScalingConfig(),
        )

        snapshots = {str(aid): _make_snapshot(str(aid)) for aid in AGENT_IDS}
        decisions = await service.evaluate(
            agent_ids=AGENT_IDS,
            context_kwargs={
                "performance_kwargs": {"snapshots": snapshots},
            },
        )

        prune_decisions = [
            d for d in decisions if d.action_type == ScalingActionType.PRUNE
        ]
        assert len(prune_decisions) == 0

    async def test_prunes_when_evolution_not_active(self) -> None:
        """Agent without active evolution is pruned normally."""

        async def _never_adapting(agent_id: str) -> bool:
            return False

        strategy = PerformancePruningStrategy(
            policy=_StubPruningPolicy(),
            evolution_checker=_never_adapting,
            defer_during_evolution=True,
        )

        guard = CompositeScalingGuard(
            guards=(ConflictResolver(),),
        )

        service = ScalingService(
            strategies=(strategy,),
            guard=guard,
            context_builder=ScalingContextBuilder(),
            config=ScalingConfig(),
        )

        snapshots = {str(aid): _make_snapshot(str(aid)) for aid in AGENT_IDS}
        decisions = await service.evaluate(
            agent_ids=AGENT_IDS,
            context_kwargs={
                "performance_kwargs": {"snapshots": snapshots},
            },
        )
        prune_decisions = [
            d for d in decisions if d.action_type == ScalingActionType.PRUNE
        ]
        assert len(prune_decisions) >= 1
