"""Tests for Reliability/Resilience pillar strategy."""

import pytest

from synthorg.hr.evaluation.config import EvaluationConfig, ResilienceConfig
from synthorg.hr.evaluation.enums import EvaluationPillar
from synthorg.hr.evaluation.resilience_strategy import TaskBasedResilienceStrategy
from tests.unit.hr.evaluation.conftest import (
    make_evaluation_context,
    make_resilience_metrics,
)

pytestmark = pytest.mark.unit


@pytest.fixture
def strategy() -> TaskBasedResilienceStrategy:
    return TaskBasedResilienceStrategy()


class TestTaskBasedResilienceStrategy:
    """TaskBasedResilienceStrategy tests."""

    def test_protocol_properties(self, strategy: TaskBasedResilienceStrategy) -> None:
        assert strategy.name == "task_based_resilience"
        assert strategy.pillar == EvaluationPillar.RESILIENCE

    async def test_no_metrics_returns_neutral(
        self,
        strategy: TaskBasedResilienceStrategy,
    ) -> None:
        ctx = make_evaluation_context()
        result = await strategy.score(context=ctx)
        assert result.score == 5.0
        assert result.confidence == 0.0

    async def test_all_metrics_enabled(
        self,
        strategy: TaskBasedResilienceStrategy,
    ) -> None:
        rm = make_resilience_metrics(
            total_tasks=20,
            failed_tasks=3,
            recovered_tasks=2,
            current_success_streak=5,
            longest_success_streak=10,
            quality_score_stddev=1.0,
        )
        ctx = make_evaluation_context()
        ctx = ctx.model_copy(update={"resilience_metrics": rm})
        result = await strategy.score(context=ctx)
        assert result.pillar == EvaluationPillar.RESILIENCE
        assert result.score > 0.0
        assert result.confidence > 0.0
        assert len(result.breakdown) == 4

    async def test_perfect_agent(
        self,
        strategy: TaskBasedResilienceStrategy,
    ) -> None:
        rm = make_resilience_metrics(
            total_tasks=20,
            failed_tasks=0,
            recovered_tasks=0,
            current_success_streak=20,
            longest_success_streak=20,
            quality_score_stddev=0.0,
        )
        ctx = make_evaluation_context()
        ctx = ctx.model_copy(update={"resilience_metrics": rm})
        result = await strategy.score(context=ctx)
        assert result.score >= 9.5

    async def test_all_failures(
        self,
        strategy: TaskBasedResilienceStrategy,
    ) -> None:
        rm = make_resilience_metrics(
            total_tasks=10,
            failed_tasks=10,
            recovered_tasks=0,
            current_success_streak=0,
            longest_success_streak=0,
            quality_score_stddev=3.0,
        )
        ctx = make_evaluation_context()
        ctx = ctx.model_copy(update={"resilience_metrics": rm})
        result = await strategy.score(context=ctx)
        assert result.score < 2.0

    async def test_success_rate_disabled(
        self,
        strategy: TaskBasedResilienceStrategy,
    ) -> None:
        cfg = EvaluationConfig(
            resilience=ResilienceConfig(success_rate_enabled=False),
        )
        rm = make_resilience_metrics()
        ctx = make_evaluation_context(config=cfg)
        ctx = ctx.model_copy(update={"resilience_metrics": rm})
        result = await strategy.score(context=ctx)
        # Should have 3 components instead of 4.
        assert len(result.breakdown) == 3
        assert not any(k == "success_rate" for k, _ in result.breakdown)

    async def test_only_streak_enabled(
        self,
        strategy: TaskBasedResilienceStrategy,
    ) -> None:
        cfg = EvaluationConfig(
            resilience=ResilienceConfig(
                success_rate_enabled=False,
                recovery_rate_enabled=False,
                consistency_enabled=False,
            ),
        )
        rm = make_resilience_metrics(current_success_streak=8, longest_success_streak=8)
        ctx = make_evaluation_context(config=cfg)
        ctx = ctx.model_copy(update={"resilience_metrics": rm})
        result = await strategy.score(context=ctx)
        assert len(result.breakdown) == 1
        assert result.breakdown[0][0] == "streak"

    async def test_zero_tasks_returns_neutral(
        self,
        strategy: TaskBasedResilienceStrategy,
    ) -> None:
        rm = make_resilience_metrics(
            total_tasks=0,
            failed_tasks=0,
            recovered_tasks=0,
            current_success_streak=0,
            longest_success_streak=0,
            quality_score_stddev=None,
        )
        ctx = make_evaluation_context()
        ctx = ctx.model_copy(update={"resilience_metrics": rm})
        result = await strategy.score(context=ctx)
        assert result.score == 5.0
        assert result.confidence == 0.0
