"""Tests for User Experience pillar strategy."""

import pytest

from synthorg.hr.evaluation.config import EvaluationConfig, ExperienceConfig
from synthorg.hr.evaluation.enums import EvaluationPillar
from synthorg.hr.evaluation.experience_strategy import FeedbackBasedUxStrategy
from tests.unit.hr.evaluation.conftest import (
    make_evaluation_context,
    make_interaction_feedback,
)

pytestmark = pytest.mark.unit


@pytest.fixture
def strategy() -> FeedbackBasedUxStrategy:
    return FeedbackBasedUxStrategy()


class TestFeedbackBasedUxStrategy:
    """FeedbackBasedUxStrategy tests."""

    def test_protocol_properties(self, strategy: FeedbackBasedUxStrategy) -> None:
        assert strategy.name == "feedback_based_ux"
        assert strategy.pillar == EvaluationPillar.EXPERIENCE

    async def test_insufficient_feedback_returns_neutral(
        self,
        strategy: FeedbackBasedUxStrategy,
    ) -> None:
        """Below min_feedback_count returns neutral with 0 confidence."""
        fb = (make_interaction_feedback(),)  # Only 1, min is 3.
        ctx = make_evaluation_context()
        ctx = ctx.model_copy(update={"feedback": fb})
        result = await strategy.score(context=ctx)
        assert result.score == 5.0
        assert result.confidence == 0.0

    async def test_all_dimensions_present(
        self,
        strategy: FeedbackBasedUxStrategy,
    ) -> None:
        fb = tuple(make_interaction_feedback() for _ in range(5))
        ctx = make_evaluation_context()
        ctx = ctx.model_copy(update={"feedback": fb})
        result = await strategy.score(context=ctx)
        assert result.pillar == EvaluationPillar.EXPERIENCE
        assert result.score > 0.0
        assert result.confidence > 0.0
        assert len(result.breakdown) == 5

    async def test_high_ratings_produce_high_score(
        self,
        strategy: FeedbackBasedUxStrategy,
    ) -> None:
        fb = tuple(
            make_interaction_feedback(
                clarity_rating=1.0,
                tone_rating=1.0,
                helpfulness_rating=1.0,
                trust_rating=1.0,
                satisfaction_rating=1.0,
            )
            for _ in range(5)
        )
        ctx = make_evaluation_context()
        ctx = ctx.model_copy(update={"feedback": fb})
        result = await strategy.score(context=ctx)
        assert result.score >= 9.5

    async def test_low_ratings_produce_low_score(
        self,
        strategy: FeedbackBasedUxStrategy,
    ) -> None:
        fb = tuple(
            make_interaction_feedback(
                clarity_rating=0.1,
                tone_rating=0.1,
                helpfulness_rating=0.1,
                trust_rating=0.1,
                satisfaction_rating=0.1,
            )
            for _ in range(5)
        )
        ctx = make_evaluation_context()
        ctx = ctx.model_copy(update={"feedback": fb})
        result = await strategy.score(context=ctx)
        assert result.score < 2.0

    async def test_partial_feedback_redistributes(
        self,
        strategy: FeedbackBasedUxStrategy,
    ) -> None:
        """Feedback with some None ratings still produces a score."""
        fb = tuple(
            make_interaction_feedback(
                clarity_rating=0.9,
                tone_rating=None,
                helpfulness_rating=0.8,
                trust_rating=None,
                satisfaction_rating=None,
            )
            for _ in range(3)
        )
        ctx = make_evaluation_context()
        ctx = ctx.model_copy(update={"feedback": fb})
        result = await strategy.score(context=ctx)
        assert result.score > 0.0
        # Only clarity and helpfulness should appear.
        assert len(result.breakdown) == 2

    async def test_tone_disabled(
        self,
        strategy: FeedbackBasedUxStrategy,
    ) -> None:
        cfg = EvaluationConfig(
            experience=ExperienceConfig(tone_enabled=False),
        )
        fb = tuple(make_interaction_feedback() for _ in range(3))
        ctx = make_evaluation_context(config=cfg)
        ctx = ctx.model_copy(update={"feedback": fb})
        result = await strategy.score(context=ctx)
        assert not any(k == "tone" for k, _ in result.breakdown)
        # Should have 4 components instead of 5.
        assert len(result.breakdown) == 4

    async def test_all_metrics_disabled_returns_neutral(
        self,
        strategy: FeedbackBasedUxStrategy,
    ) -> None:
        cfg = EvaluationConfig(
            experience=ExperienceConfig(
                enabled=False,
                clarity_enabled=False,
                tone_enabled=False,
                helpfulness_enabled=False,
                trust_enabled=False,
                satisfaction_enabled=False,
            ),
        )
        fb = tuple(make_interaction_feedback() for _ in range(5))
        ctx = make_evaluation_context(config=cfg)
        ctx = ctx.model_copy(update={"feedback": fb})
        result = await strategy.score(context=ctx)
        assert result.score == 5.0
        assert result.confidence == 0.0

    async def test_custom_min_feedback_count(
        self,
        strategy: FeedbackBasedUxStrategy,
    ) -> None:
        cfg = EvaluationConfig(
            experience=ExperienceConfig(min_feedback_count=1),
        )
        fb = (make_interaction_feedback(),)
        ctx = make_evaluation_context(config=cfg)
        ctx = ctx.model_copy(update={"feedback": fb})
        result = await strategy.score(context=ctx)
        assert result.score > 0.0
        assert result.confidence > 0.0
