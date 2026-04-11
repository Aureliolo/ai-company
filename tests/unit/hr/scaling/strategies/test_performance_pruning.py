"""Tests for performance pruning strategy."""

import pytest

from synthorg.core.types import NotBlankStr
from synthorg.hr.enums import TrendDirection
from synthorg.hr.performance.models import (
    AgentPerformanceSnapshot,
    TrendResult,
    WindowMetrics,
)
from synthorg.hr.pruning.models import PruningEvaluation
from synthorg.hr.scaling.enums import ScalingActionType
from synthorg.hr.scaling.strategies.performance_pruning import (
    PerformancePruningStrategy,
)

from .conftest import NOW, make_context

_AGENT_IDS = ("agent-001", "agent-002")


def _make_snapshot(agent_id: str) -> AgentPerformanceSnapshot:
    return AgentPerformanceSnapshot(
        agent_id=NotBlankStr(agent_id),
        computed_at=NOW,
        windows=(
            WindowMetrics(
                window_size=NotBlankStr("7d"),
                data_point_count=10,
                tasks_completed=8,
                tasks_failed=2,
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


class _StubPruningPolicy:
    """Stub policy that marks all agents as eligible."""

    def __init__(self, *, eligible: bool = True) -> None:
        self._eligible = eligible

    async def evaluate(
        self,
        agent_id: NotBlankStr,
        snapshot: AgentPerformanceSnapshot,
    ) -> PruningEvaluation:
        return PruningEvaluation(
            agent_id=agent_id,
            eligible=self._eligible,
            reasons=(NotBlankStr("below threshold"),) if self._eligible else (),
            scores={"quality": 2.0},
            policy_name=NotBlankStr("stub"),
            snapshot=snapshot,
            evaluated_at=NOW,
        )


@pytest.mark.unit
class TestPerformancePruningStrategy:
    """PerformancePruningStrategy decision logic."""

    async def test_eligible_agents_produce_prune(self) -> None:
        policy = _StubPruningPolicy(eligible=True)
        strategy = PerformancePruningStrategy(policy=policy)
        ctx = make_context(agent_ids=_AGENT_IDS)
        snapshots = {aid: _make_snapshot(aid) for aid in _AGENT_IDS}
        decisions = await strategy.evaluate(ctx, snapshots=snapshots)
        assert len(decisions) == 2
        assert all(d.action_type == ScalingActionType.PRUNE for d in decisions)

    async def test_ineligible_agents_produce_nothing(self) -> None:
        policy = _StubPruningPolicy(eligible=False)
        strategy = PerformancePruningStrategy(policy=policy)
        ctx = make_context(agent_ids=_AGENT_IDS)
        snapshots = {aid: _make_snapshot(aid) for aid in _AGENT_IDS}
        decisions = await strategy.evaluate(ctx, snapshots=snapshots)
        assert len(decisions) == 0

    async def test_no_snapshots_returns_empty(self) -> None:
        policy = _StubPruningPolicy()
        strategy = PerformancePruningStrategy(policy=policy)
        ctx = make_context(agent_ids=_AGENT_IDS)
        decisions = await strategy.evaluate(ctx, snapshots=None)
        assert len(decisions) == 0

    async def test_defers_during_evolution(self) -> None:
        policy = _StubPruningPolicy(eligible=True)

        async def _always_adapting(agent_id: str) -> bool:
            return True

        strategy = PerformancePruningStrategy(
            policy=policy,
            evolution_checker=_always_adapting,
            defer_during_evolution=True,
        )
        ctx = make_context(agent_ids=_AGENT_IDS)
        snapshots = {aid: _make_snapshot(aid) for aid in _AGENT_IDS}
        decisions = await strategy.evaluate(ctx, snapshots=snapshots)
        assert len(decisions) == 0

    async def test_no_deferral_when_disabled(self) -> None:
        policy = _StubPruningPolicy(eligible=True)

        async def _always_adapting(agent_id: str) -> bool:
            return True

        strategy = PerformancePruningStrategy(
            policy=policy,
            evolution_checker=_always_adapting,
            defer_during_evolution=False,
        )
        ctx = make_context(agent_ids=_AGENT_IDS)
        snapshots = {aid: _make_snapshot(aid) for aid in _AGENT_IDS}
        decisions = await strategy.evaluate(ctx, snapshots=snapshots)
        assert len(decisions) == 2

    async def test_name_and_action_types(self) -> None:
        policy = _StubPruningPolicy()
        strategy = PerformancePruningStrategy(policy=policy)
        assert strategy.name == "performance_pruning"
        assert ScalingActionType.PRUNE in strategy.action_types
