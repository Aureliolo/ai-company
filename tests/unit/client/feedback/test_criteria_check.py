"""Unit tests for CriteriaCheckFeedback strategy."""

import pytest

from synthorg.client.feedback import CriteriaCheckFeedback
from synthorg.client.models import ReviewContext
from synthorg.client.protocols import FeedbackStrategy

pytestmark = pytest.mark.unit


def _make_context(
    *,
    deliverable: str,
    criteria: tuple[str, ...],
) -> ReviewContext:
    return ReviewContext(
        task_id="task-1",
        task_title="Example task",
        acceptance_criteria=criteria,
        deliverable_summary=deliverable,
    )


class TestCriteriaCheckFeedback:
    def test_protocol_compatible(self) -> None:
        strategy = CriteriaCheckFeedback(client_id="client-1")
        assert isinstance(strategy, FeedbackStrategy)

    async def test_all_criteria_mentioned_accepts(self) -> None:
        strategy = CriteriaCheckFeedback(client_id="client-1")
        context = _make_context(
            deliverable="Added tests pass, docs updated, and CI green",
            criteria=("tests pass", "docs updated", "CI green"),
        )
        feedback = await strategy.evaluate(context)
        assert feedback.accepted is True
        assert feedback.unmet_criteria == ()

    async def test_case_insensitive_match(self) -> None:
        strategy = CriteriaCheckFeedback(client_id="client-1")
        context = _make_context(
            deliverable="TESTS PASS and DOCS UPDATED",
            criteria=("tests pass", "docs updated"),
        )
        feedback = await strategy.evaluate(context)
        assert feedback.accepted is True

    async def test_missing_criterion_rejects(self) -> None:
        strategy = CriteriaCheckFeedback(client_id="client-1")
        context = _make_context(
            deliverable="Added tests pass",
            criteria=("tests pass", "docs updated"),
        )
        feedback = await strategy.evaluate(context)
        assert feedback.accepted is False
        assert feedback.unmet_criteria == ("docs updated",)
        assert feedback.reason is not None
        assert "1 of 2" in feedback.reason

    async def test_empty_criteria_accepts(self) -> None:
        strategy = CriteriaCheckFeedback(client_id="client-1")
        context = _make_context(
            deliverable="Anything at all",
            criteria=(),
        )
        feedback = await strategy.evaluate(context)
        assert feedback.accepted is True

    async def test_all_missing_criteria_reported(self) -> None:
        strategy = CriteriaCheckFeedback(client_id="client-1")
        context = _make_context(
            deliverable="irrelevant",
            criteria=("first", "second", "third"),
        )
        feedback = await strategy.evaluate(context)
        assert feedback.accepted is False
        assert len(feedback.unmet_criteria) == 3
