"""Unit tests for intake engine domain models."""

import pytest
from pydantic import ValidationError

from synthorg.engine.intake.models import IntakeResult

pytestmark = pytest.mark.unit


class TestIntakeResult:
    """Tests for the IntakeResult model."""

    def test_accepted_result(self) -> None:
        result = IntakeResult.accepted_result(
            request_id="req-1",
            task_id="task-1",
        )
        assert result.accepted is True
        assert result.task_id == "task-1"
        assert result.rejection_reason is None

    def test_rejected_result(self) -> None:
        result = IntakeResult.rejected_result(
            request_id="req-1",
            reason="Requirements unclear",
        )
        assert result.accepted is False
        assert result.task_id is None
        assert result.rejection_reason == "Requirements unclear"

    def test_direct_construction(self) -> None:
        result = IntakeResult(
            request_id="req-1",
            accepted=True,
            task_id="task-1",
        )
        assert result.request_id == "req-1"
        assert result.processed_at is not None

    def test_blank_request_id_rejected(self) -> None:
        with pytest.raises(ValidationError):
            IntakeResult(
                request_id="   ",
                accepted=True,
            )

    def test_accepted_without_task_id_rejected(self) -> None:
        with pytest.raises(ValidationError, match="task_id is required"):
            IntakeResult(
                request_id="req-1",
                accepted=True,
            )

    def test_accepted_with_rejection_reason_rejected(self) -> None:
        with pytest.raises(ValidationError, match="rejection_reason must be None"):
            IntakeResult(
                request_id="req-1",
                accepted=True,
                task_id="task-1",
                rejection_reason="should not be here",
            )

    def test_rejected_without_reason_rejected(self) -> None:
        with pytest.raises(ValidationError, match="rejection_reason is required"):
            IntakeResult(
                request_id="req-1",
                accepted=False,
            )

    def test_rejected_with_task_id_rejected(self) -> None:
        with pytest.raises(ValidationError, match="task_id must be None"):
            IntakeResult(
                request_id="req-1",
                accepted=False,
                task_id="task-1",
                rejection_reason="bad request",
            )

    def test_frozen(self) -> None:
        result = IntakeResult.accepted_result(
            request_id="req-1",
            task_id="task-1",
        )
        with pytest.raises(ValidationError):
            result.accepted = False  # type: ignore[misc]
