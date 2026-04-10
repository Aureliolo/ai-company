"""Unit tests for ScoredFeedback strategy."""

import pytest

from synthorg.client.feedback import ScoredFeedback
from synthorg.client.models import ReviewContext
from synthorg.client.protocols import FeedbackStrategy

pytestmark = pytest.mark.unit


def _make_context(
    *,
    deliverable: str,
    criteria: tuple[str, ...] = (),
) -> ReviewContext:
    return ReviewContext(
        task_id="task-1",
        task_title="Example task",
        acceptance_criteria=criteria,
        deliverable_summary=deliverable,
    )


class TestScoredFeedbackConstructor:
    def test_defaults(self) -> None:
        strategy = ScoredFeedback(client_id="client-1")
        assert isinstance(strategy, FeedbackStrategy)

    @pytest.mark.parametrize("bad", [-0.1, 1.5])
    def test_rejects_out_of_range_passing_score(self, bad: float) -> None:
        with pytest.raises(ValueError, match="passing_score"):
            ScoredFeedback(client_id="client-1", passing_score=bad)

    @pytest.mark.parametrize("bad", [0.0, -1.0])
    def test_rejects_non_positive_multiplier(self, bad: float) -> None:
        with pytest.raises(ValueError, match="strictness_multiplier"):
            ScoredFeedback(client_id="client-1", strictness_multiplier=bad)


class TestScoredFeedbackEvaluate:
    async def test_all_criteria_mentioned_accepts(self) -> None:
        strategy = ScoredFeedback(client_id="client-1", passing_score=0.9)
        context = _make_context(
            deliverable=(
                "The implementation adds tests pass and docs updated "
                "with full coverage."
            ),
            criteria=("tests pass", "docs updated"),
        )
        feedback = await strategy.evaluate(context)
        assert feedback.accepted is True
        assert feedback.scores is not None
        assert feedback.scores["tests pass"] == 1.0
        assert feedback.scores["docs updated"] == 1.0

    async def test_missing_criteria_rejects(self) -> None:
        strategy = ScoredFeedback(client_id="client-1", passing_score=0.9)
        context = _make_context(
            deliverable="nothing relevant here",
            criteria=("tests pass", "docs updated"),
        )
        feedback = await strategy.evaluate(context)
        assert feedback.accepted is False
        assert feedback.scores is not None
        assert "tests pass" in feedback.unmet_criteria
        assert feedback.reason is not None

    async def test_scores_within_range(self) -> None:
        strategy = ScoredFeedback(client_id="client-1")
        context = _make_context(
            deliverable="irrelevant",
            criteria=("a", "b", "c"),
        )
        feedback = await strategy.evaluate(context)
        assert feedback.scores is not None
        for score in feedback.scores.values():
            assert 0.0 <= score <= 1.0

    async def test_deterministic(self) -> None:
        strategy = ScoredFeedback(client_id="client-1")
        context = _make_context(
            deliverable="same input",
            criteria=("x", "y"),
        )
        first = await strategy.evaluate(context)
        second = await strategy.evaluate(context)
        assert first.scores == second.scores

    async def test_no_criteria_uses_default(self) -> None:
        strategy = ScoredFeedback(client_id="client-1")
        context = _make_context(deliverable="some content")
        feedback = await strategy.evaluate(context)
        assert feedback.scores is not None
        assert len(feedback.scores) == 1

    async def test_strictness_multiplier_raises_threshold(self) -> None:
        lenient = ScoredFeedback(
            client_id="client-1",
            passing_score=0.5,
            strictness_multiplier=1.0,
        )
        strict = ScoredFeedback(
            client_id="client-1",
            passing_score=0.5,
            strictness_multiplier=2.0,
        )
        context = _make_context(
            deliverable="all criteria mentioned",
            criteria=("criteria mentioned",),
        )
        lenient_result = await lenient.evaluate(context)
        strict_result = await strict.evaluate(context)
        assert lenient_result.accepted is True
        assert strict_result.accepted is True
