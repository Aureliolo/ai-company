"""Unit tests for BinaryFeedback strategy."""

import pytest
from hypothesis import given
from hypothesis import strategies as st

from synthorg.client.feedback import BinaryFeedback
from synthorg.client.models import ClientFeedback, ReviewContext
from synthorg.client.protocols import FeedbackStrategy

pytestmark = pytest.mark.unit


def _make_context(
    *,
    deliverable: str = "A" * 100,
    criteria: tuple[str, ...] = (),
) -> ReviewContext:
    return ReviewContext(
        task_id="task-1",
        task_title="Example task",
        acceptance_criteria=criteria,
        deliverable_summary=deliverable,
    )


class TestBinaryFeedbackConstructor:
    def test_defaults(self) -> None:
        strategy = BinaryFeedback(client_id="client-1")
        assert isinstance(strategy, FeedbackStrategy)

    def test_rejects_non_positive_multiplier(self) -> None:
        with pytest.raises(ValueError, match="strictness_multiplier"):
            BinaryFeedback(client_id="client-1", strictness_multiplier=0.0)
        with pytest.raises(ValueError, match="strictness_multiplier"):
            BinaryFeedback(client_id="client-1", strictness_multiplier=-1.0)


class TestBinaryFeedbackEvaluate:
    async def test_accepts_long_summary(self) -> None:
        strategy = BinaryFeedback(client_id="client-1")
        feedback = await strategy.evaluate(_make_context(deliverable="x" * 500))
        assert feedback.accepted is True
        assert feedback.reason is None
        assert feedback.client_id == "client-1"
        assert feedback.task_id == "task-1"

    async def test_rejects_short_summary(self) -> None:
        strategy = BinaryFeedback(client_id="client-1")
        feedback = await strategy.evaluate(_make_context(deliverable="short"))
        assert feedback.accepted is False
        assert feedback.reason is not None
        assert "too brief" in feedback.reason

    async def test_unmet_criteria_carried_on_rejection(self) -> None:
        strategy = BinaryFeedback(client_id="client-1")
        criteria = ("Tests pass", "Docs updated")
        feedback = await strategy.evaluate(
            _make_context(deliverable="short", criteria=criteria)
        )
        assert feedback.accepted is False
        assert feedback.unmet_criteria == criteria

    async def test_higher_strictness_raises_threshold(self) -> None:
        low = BinaryFeedback(client_id="client-1", strictness_multiplier=1.0)
        high = BinaryFeedback(client_id="client-1", strictness_multiplier=10.0)
        context = _make_context(deliverable="x" * 80)
        low_result = await low.evaluate(context)
        high_result = await high.evaluate(context)
        assert low_result.accepted is True
        assert high_result.accepted is False

    @pytest.mark.parametrize("length", [0, 1, 10, 19])
    async def test_various_short_summaries_rejected(self, length: int) -> None:
        strategy = BinaryFeedback(client_id="client-1")
        # Make sure the summary is not blank -- ReviewContext forbids that.
        if length == 0:
            pytest.skip("ReviewContext forbids blank deliverable")
        feedback = await strategy.evaluate(_make_context(deliverable="x" * length))
        assert feedback.accepted is False


class TestBinaryFeedbackProperties:
    @given(
        summary=st.text(min_size=1, max_size=500).filter(lambda s: s.strip()),
        multiplier=st.floats(
            min_value=0.1, max_value=10.0, allow_nan=False, allow_infinity=False
        ),
    )
    async def test_always_returns_valid_feedback(
        self, summary: str, multiplier: float
    ) -> None:
        strategy = BinaryFeedback(
            client_id="client-1", strictness_multiplier=multiplier
        )
        feedback = await strategy.evaluate(
            ReviewContext(
                task_id="task-1",
                task_title="T",
                deliverable_summary=summary,
            )
        )
        assert isinstance(feedback, ClientFeedback)
        assert feedback.client_id == "client-1"
        # Every rejection must have a reason (Pydantic would enforce this too)
        if not feedback.accepted:
            assert feedback.reason is not None
