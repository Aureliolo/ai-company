"""Unit tests for ReviewGateService -- IN_REVIEW task transitions."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, PropertyMock

import pytest

from synthorg.core.enums import DecisionOutcome, Priority, TaskStatus, TaskType
from synthorg.core.task import AcceptanceCriterion, Task
from synthorg.engine.decisions import DecisionRecord
from synthorg.engine.errors import SelfReviewError
from synthorg.engine.review_gate import ReviewGateService
from synthorg.engine.task_engine_models import TaskMutationResult


def _make_mock_task_engine(
    return_value: TaskMutationResult | None = None,
    *,
    task: Task | None = None,
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
    mock_te.get_task = AsyncMock(return_value=task)
    return mock_te


def _make_mock_decision_repo(
    existing: tuple[DecisionRecord, ...] = (),
) -> MagicMock:
    """Build a mock DecisionRepository."""
    repo = MagicMock()
    repo.append = AsyncMock(return_value=None)
    repo.list_by_task = AsyncMock(return_value=existing)
    repo.get = AsyncMock(return_value=None)
    repo.list_by_agent = AsyncMock(return_value=())
    return repo


def _make_mock_persistence(repo: MagicMock) -> MagicMock:
    """Build a mock PersistenceBackend with a decision_records property."""
    persistence = MagicMock()
    type(persistence).decision_records = PropertyMock(return_value=repo)
    return persistence


def _make_task(
    *,
    task_id: str = "task-1",
    assigned_to: str | None = "alice",
    criteria: tuple[str, ...] = ("Login works", "Tests pass"),
    status: TaskStatus = TaskStatus.IN_REVIEW,
) -> Task:
    """Build a Task with configurable fields."""
    return Task(
        id=task_id,
        title="Test task",
        description="Test task description",
        type=TaskType.DEVELOPMENT,
        priority=Priority.HIGH,
        project="proj-1",
        created_by="manager",
        assigned_to=assigned_to,
        status=status,
        acceptance_criteria=tuple(AcceptanceCriterion(description=c) for c in criteria),
    )


@pytest.mark.unit
class TestReviewGateServiceApprove:
    """Tests for the approve flow."""

    async def test_approve_transitions_to_completed(self) -> None:
        """Approving a review syncs COMPLETED status to task engine."""
        task = _make_task()
        mock_te = _make_mock_task_engine(task=task)
        repo = _make_mock_decision_repo()
        service = ReviewGateService(
            task_engine=mock_te,
            persistence=_make_mock_persistence(repo),
        )

        await service.complete_review(
            task_id="task-1",
            requested_by="bob",
            approved=True,
            decided_by="bob",
        )

        mock_te.submit.assert_awaited_once()
        mutation = mock_te.submit.call_args.args[0]
        assert mutation.target_status == TaskStatus.COMPLETED
        assert "approved" in mutation.reason.lower()
        assert "bob" in mutation.reason

    async def test_reject_transitions_to_in_progress(self) -> None:
        """Rejecting a review syncs IN_PROGRESS status to task engine."""
        task = _make_task()
        mock_te = _make_mock_task_engine(task=task)
        repo = _make_mock_decision_repo()
        service = ReviewGateService(
            task_engine=mock_te, persistence=_make_mock_persistence(repo)
        )

        await service.complete_review(
            task_id="task-1",
            requested_by="bob",
            approved=False,
            decided_by="bob",
            reason="needs rework on error handling",
        )

        mock_te.submit.assert_awaited_once()
        mutation = mock_te.submit.call_args.args[0]
        assert mutation.target_status == TaskStatus.IN_PROGRESS
        assert "rejected" in mutation.reason.lower()
        assert "needs rework on error handling" in mutation.reason

    async def test_reject_without_reason(self) -> None:
        """Rejecting without a reason still works."""
        task = _make_task()
        mock_te = _make_mock_task_engine(task=task)
        repo = _make_mock_decision_repo()
        service = ReviewGateService(
            task_engine=mock_te, persistence=_make_mock_persistence(repo)
        )

        await service.complete_review(
            task_id="task-1",
            requested_by="bob",
            approved=False,
            decided_by="bob",
        )

        mutation = mock_te.submit.call_args.args[0]
        assert mutation.target_status == TaskStatus.IN_PROGRESS
        assert "None" not in mutation.reason


@pytest.mark.unit
class TestReviewGateServiceSelfReview:
    """Tests for self-review prevention."""

    async def test_self_review_raises(self) -> None:
        """When decided_by == task.assigned_to, SelfReviewError is raised."""
        task = _make_task(assigned_to="alice")
        mock_te = _make_mock_task_engine(task=task)
        repo = _make_mock_decision_repo()
        service = ReviewGateService(
            task_engine=mock_te, persistence=_make_mock_persistence(repo)
        )

        with pytest.raises(SelfReviewError) as exc_info:
            await service.complete_review(
                task_id="task-1",
                requested_by="alice",
                approved=True,
                decided_by="alice",
            )

        assert exc_info.value.task_id == "task-1"
        assert exc_info.value.agent_id == "alice"
        # No transition should have been attempted
        mock_te.submit.assert_not_awaited()
        repo.append.assert_not_awaited()

    async def test_different_reviewer_allowed(self) -> None:
        """When decided_by != task.assigned_to, review proceeds normally."""
        task = _make_task(assigned_to="alice")
        mock_te = _make_mock_task_engine(task=task)
        repo = _make_mock_decision_repo()
        service = ReviewGateService(
            task_engine=mock_te, persistence=_make_mock_persistence(repo)
        )

        await service.complete_review(
            task_id="task-1",
            requested_by="bob",
            approved=True,
            decided_by="bob",
        )

        mock_te.submit.assert_awaited_once()

    async def test_task_not_found_raises(self) -> None:
        """When task does not exist, the review cannot complete."""
        mock_te = _make_mock_task_engine(task=None)
        repo = _make_mock_decision_repo()
        service = ReviewGateService(
            task_engine=mock_te, persistence=_make_mock_persistence(repo)
        )

        from synthorg.engine.errors import TaskNotFoundError

        with pytest.raises(TaskNotFoundError):
            await service.complete_review(
                task_id="task-nonexistent",
                requested_by="bob",
                approved=True,
                decided_by="bob",
            )

    async def test_task_without_assignee_proceeds(self) -> None:
        """When task.assigned_to is None, self-review check is skipped."""
        task = _make_task(assigned_to=None, status=TaskStatus.CREATED)
        mock_te = _make_mock_task_engine(task=task)
        repo = _make_mock_decision_repo()
        service = ReviewGateService(
            task_engine=mock_te, persistence=_make_mock_persistence(repo)
        )

        # Should not raise (no assignee to enforce against)
        await service.complete_review(
            task_id="task-1",
            requested_by="bob",
            approved=True,
            decided_by="bob",
        )
        mock_te.submit.assert_awaited_once()


@pytest.mark.unit
class TestReviewGateServiceDecisionRecording:
    """Tests for decision record append on complete_review."""

    async def test_approve_records_decision(self) -> None:
        """Approving appends a DecisionRecord with APPROVED outcome."""
        task = _make_task()
        mock_te = _make_mock_task_engine(task=task)
        repo = _make_mock_decision_repo()
        service = ReviewGateService(
            task_engine=mock_te, persistence=_make_mock_persistence(repo)
        )

        await service.complete_review(
            task_id="task-1",
            requested_by="bob",
            approved=True,
            decided_by="bob",
        )

        repo.append.assert_awaited_once()
        record: DecisionRecord = repo.append.call_args.args[0]
        assert isinstance(record, DecisionRecord)
        assert record.task_id == "task-1"
        assert record.executing_agent_id == "alice"
        assert record.reviewer_agent_id == "bob"
        assert record.decision is DecisionOutcome.APPROVED
        assert record.version == 1

    async def test_reject_records_decision(self) -> None:
        """Rejecting appends a DecisionRecord with REJECTED outcome."""
        task = _make_task()
        mock_te = _make_mock_task_engine(task=task)
        repo = _make_mock_decision_repo()
        service = ReviewGateService(
            task_engine=mock_te, persistence=_make_mock_persistence(repo)
        )

        await service.complete_review(
            task_id="task-1",
            requested_by="bob",
            approved=False,
            decided_by="bob",
            reason="needs rework",
        )

        record: DecisionRecord = repo.append.call_args.args[0]
        assert record.decision is DecisionOutcome.REJECTED
        assert record.reason == "needs rework"

    async def test_decision_includes_criteria_snapshot(self) -> None:
        """Decision record includes acceptance criteria descriptions."""
        task = _make_task(criteria=("JWT login", "Refresh works"))
        mock_te = _make_mock_task_engine(task=task)
        repo = _make_mock_decision_repo()
        service = ReviewGateService(
            task_engine=mock_te, persistence=_make_mock_persistence(repo)
        )

        await service.complete_review(
            task_id="task-1",
            requested_by="bob",
            approved=True,
            decided_by="bob",
        )

        record: DecisionRecord = repo.append.call_args.args[0]
        assert record.criteria_snapshot == ("JWT login", "Refresh works")

    async def test_decision_version_monotonic_per_task(self) -> None:
        """version increments based on existing decisions for the task."""
        existing = (
            DecisionRecord(
                id="d-1",
                task_id="task-1",
                executing_agent_id="alice",
                reviewer_agent_id="carol",
                decision=DecisionOutcome.REJECTED,
                recorded_at=datetime(2026, 4, 4, 10, 0, tzinfo=UTC),
                version=1,
                metadata={},
            ),
        )
        task = _make_task()
        mock_te = _make_mock_task_engine(task=task)
        repo = _make_mock_decision_repo(existing=existing)
        service = ReviewGateService(
            task_engine=mock_te, persistence=_make_mock_persistence(repo)
        )

        await service.complete_review(
            task_id="task-1",
            requested_by="bob",
            approved=True,
            decided_by="bob",
        )

        record: DecisionRecord = repo.append.call_args.args[0]
        assert record.version == 2

    async def test_decision_record_failure_is_non_fatal(self) -> None:
        """If the decision repo append fails, the review still completes."""
        task = _make_task()
        mock_te = _make_mock_task_engine(task=task)
        repo = _make_mock_decision_repo()
        repo.append = AsyncMock(side_effect=RuntimeError("disk full"))
        service = ReviewGateService(
            task_engine=mock_te, persistence=_make_mock_persistence(repo)
        )

        # Should NOT raise
        await service.complete_review(
            task_id="task-1",
            requested_by="bob",
            approved=True,
            decided_by="bob",
        )
        # Transition still happened
        mock_te.submit.assert_awaited_once()
