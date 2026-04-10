"""Unit tests for AdversarialFeedback strategy."""

import pytest

from synthorg.client.feedback import AdversarialFeedback
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


class TestAdversarialFeedbackConstructor:
    def test_protocol_compatible(self) -> None:
        strategy = AdversarialFeedback(client_id="client-1")
        assert isinstance(strategy, FeedbackStrategy)

    def test_rejects_non_positive_min_length(self) -> None:
        with pytest.raises(ValueError, match="min_length"):
            AdversarialFeedback(client_id="client-1", min_length=0)

    def test_rejects_non_positive_min_words(self) -> None:
        with pytest.raises(ValueError, match="min_words"):
            AdversarialFeedback(client_id="client-1", min_words=-1)


class TestAdversarialFeedbackEvaluate:
    async def test_rejects_short_summary(self) -> None:
        strategy = AdversarialFeedback(
            client_id="client-1", min_length=100, min_words=5
        )
        feedback = await strategy.evaluate(
            _make_context(deliverable="too short summary")
        )
        assert feedback.accepted is False
        assert feedback.reason is not None
        assert "shorter than" in feedback.reason

    async def test_rejects_low_vocabulary(self) -> None:
        strategy = AdversarialFeedback(
            client_id="client-1", min_length=10, min_words=20
        )
        feedback = await strategy.evaluate(
            _make_context(deliverable="a a a a a a a a a a a a")
        )
        assert feedback.accepted is False
        assert feedback.reason is not None
        assert "distinct words" in feedback.reason

    async def test_rejects_missing_criteria(self) -> None:
        strategy = AdversarialFeedback(client_id="client-1", min_length=10, min_words=1)
        feedback = await strategy.evaluate(
            _make_context(
                deliverable="substantial content here",
                criteria=("rigorous testing",),
            )
        )
        assert feedback.accepted is False
        assert "rigorous testing" in feedback.unmet_criteria

    async def test_accepts_when_all_conditions_met(self) -> None:
        strategy = AdversarialFeedback(client_id="client-1", min_length=30, min_words=3)
        deliverable = (
            "implementation includes complete testing coverage with "
            "full documentation updates"
        )
        feedback = await strategy.evaluate(
            _make_context(
                deliverable=deliverable,
                criteria=("testing", "documentation"),
            )
        )
        assert feedback.accepted is True
        assert feedback.unmet_criteria == ()

    async def test_stricter_than_criteria_check(self) -> None:
        """Given identical inputs, adversarial rejects where criteria_check accepts."""
        from synthorg.client.feedback import CriteriaCheckFeedback

        criteria = ("coverage",)
        deliverable = "coverage"  # mentions criterion but very short

        adversarial = AdversarialFeedback(
            client_id="client-1", min_length=100, min_words=5
        )
        basic = CriteriaCheckFeedback(client_id="client-1")

        adv_feedback = await adversarial.evaluate(
            _make_context(deliverable=deliverable, criteria=criteria)
        )
        basic_feedback = await basic.evaluate(
            _make_context(deliverable=deliverable, criteria=criteria)
        )
        assert adv_feedback.accepted is False
        assert basic_feedback.accepted is True
