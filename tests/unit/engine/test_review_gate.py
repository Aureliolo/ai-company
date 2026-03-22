"""Unit tests for ReviewGateService -- IN_REVIEW task transitions."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from synthorg.core.enums import TaskStatus
from synthorg.engine.review_gate import ReviewGateService
from synthorg.engine.task_engine_models import TaskMutationResult


def _make_mock_task_engine(
    return_value: TaskMutationResult | None = None,
) -> MagicMock:
    """Build a mock TaskEngine with configurable submit behavior."""
    mock_te = MagicMock()
    mock_te.submit = AsyncMock(
        return_value=return_value
        or TaskMutationResult(
            request_id="test",
            success=True,
            version=1,
        ),
    )
    return mock_te


@pytest.mark.unit
class TestReviewGateService:
    """Tests for ReviewGateService.complete_review."""

    async def test_approve_transitions_to_completed(self) -> None:
        """Approving a review syncs COMPLETED status to task engine."""
        mock_te = _make_mock_task_engine()
        service = ReviewGateService(task_engine=mock_te)

        await service.complete_review(
            task_id="task-1",
            requested_by="reviewer-1",
            approved=True,
            decided_by="reviewer-1",
        )

        mock_te.submit.assert_awaited_once()
        mutation = mock_te.submit.call_args.args[0]
        assert mutation.target_status == TaskStatus.COMPLETED
        assert "approved" in mutation.reason.lower()
        assert "reviewer-1" in mutation.reason

    async def test_reject_transitions_to_in_progress(self) -> None:
        """Rejecting a review syncs IN_PROGRESS status to task engine."""
        mock_te = _make_mock_task_engine()
        service = ReviewGateService(task_engine=mock_te)

        await service.complete_review(
            task_id="task-1",
            requested_by="reviewer-1",
            approved=False,
            decided_by="reviewer-1",
            reason="needs rework on error handling",
        )

        mock_te.submit.assert_awaited_once()
        mutation = mock_te.submit.call_args.args[0]
        assert mutation.target_status == TaskStatus.IN_PROGRESS
        assert "rejected" in mutation.reason.lower()
        assert "reviewer-1" in mutation.reason
        assert "needs rework on error handling" in mutation.reason

    async def test_reject_without_reason(self) -> None:
        """Rejecting without a reason still works."""
        mock_te = _make_mock_task_engine()
        service = ReviewGateService(task_engine=mock_te)

        await service.complete_review(
            task_id="task-1",
            requested_by="reviewer-1",
            approved=False,
            decided_by="reviewer-1",
        )

        mutation = mock_te.submit.call_args.args[0]
        assert mutation.target_status == TaskStatus.IN_PROGRESS
        # Reason should NOT contain a trailing ": None"
        assert "None" not in mutation.reason

    async def test_no_task_engine_is_noop(self) -> None:
        """When task_engine is None, complete_review is a no-op."""
        service = ReviewGateService(task_engine=None)

        # Should not raise
        await service.complete_review(
            task_id="task-1",
            requested_by="reviewer-1",
            approved=True,
            decided_by="reviewer-1",
        )
