"""Unit tests for the TaskClaim model.

TaskClaim is the wire format between dispatcher and worker. These
tests pin down the field constraints that are enforced by Pydantic
validators plus the defaults + immutability guarantees.
"""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from synthorg.workers.claim import TaskClaim, TaskClaimStatus


class TestTaskClaim:
    """TaskClaim model validation."""

    @pytest.mark.unit
    def test_minimal_valid_claim(self) -> None:
        claim = TaskClaim(task_id="task-1", new_status="assigned")
        assert claim.task_id == "task-1"
        assert claim.new_status == "assigned"
        assert claim.project_id is None
        assert claim.previous_status is None
        assert claim.dispatched_at.tzinfo is not None

    @pytest.mark.unit
    def test_rejects_empty_task_id(self) -> None:
        with pytest.raises(ValidationError):
            TaskClaim(task_id="", new_status="assigned")

    @pytest.mark.unit
    def test_rejects_whitespace_task_id(self) -> None:
        with pytest.raises(ValidationError):
            TaskClaim(task_id="   ", new_status="assigned")

    @pytest.mark.unit
    def test_rejects_empty_new_status(self) -> None:
        with pytest.raises(ValidationError):
            TaskClaim(task_id="task-1", new_status="")

    @pytest.mark.unit
    def test_accepts_optional_project_id(self) -> None:
        claim = TaskClaim(
            task_id="task-1",
            project_id="project-42",
            new_status="assigned",
        )
        assert claim.project_id == "project-42"

    @pytest.mark.unit
    def test_explicit_dispatched_at(self) -> None:
        ts = datetime(2026, 4, 10, 12, 0, 0, tzinfo=UTC)
        claim = TaskClaim(
            task_id="task-1",
            new_status="assigned",
            dispatched_at=ts,
        )
        assert claim.dispatched_at == ts

    @pytest.mark.unit
    def test_is_frozen(self) -> None:
        claim = TaskClaim(task_id="task-1", new_status="assigned")
        with pytest.raises(ValidationError):
            claim.task_id = "task-2"  # type: ignore[misc]

    @pytest.mark.unit
    def test_json_round_trip(self) -> None:
        original = TaskClaim(
            task_id="task-1",
            project_id="project-1",
            previous_status="created",
            new_status="assigned",
        )
        raw = original.model_dump_json()
        restored = TaskClaim.model_validate_json(raw)
        assert restored == original


class TestTaskClaimStatus:
    """TaskClaimStatus enum covers all worker outcomes."""

    @pytest.mark.unit
    def test_enum_members(self) -> None:
        assert TaskClaimStatus.SUCCESS.value == "success"
        assert TaskClaimStatus.FAILED.value == "failed"
        assert TaskClaimStatus.RETRY.value == "retry"

    @pytest.mark.unit
    def test_member_count(self) -> None:
        assert len(TaskClaimStatus) == 3
