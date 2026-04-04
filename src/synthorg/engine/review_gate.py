"""Review gate service -- IN_REVIEW task transitions on approval decisions.

Handles the post-execution review gate: when a human approves or rejects
a completed task, this service transitions it from IN_REVIEW to COMPLETED
(approve) or IN_PROGRESS (reject/rework) via the TaskEngine.

Enforces structural no-self-review at the approval gate boundary:
the decider must not be the same agent as the task's original executor.
Every decision is appended to the auditable decisions drop-box.

The preflight ``check_can_decide`` method lets the API controller run
the self-review check and task lookup *before* persisting the approval
decision, so a self-review attempt never leaves a decided approval row
or a broadcast WebSocket event behind.
"""

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from synthorg.core.enums import DecisionOutcome, TaskStatus
from synthorg.engine.errors import SelfReviewError, TaskNotFoundError
from synthorg.engine.task_sync import sync_to_task_engine
from synthorg.observability import get_logger
from synthorg.observability.events.approval_gate import (
    APPROVAL_GATE_DECISION_RECORD_FAILED,
    APPROVAL_GATE_DECISION_RECORDED,
    APPROVAL_GATE_REVIEW_COMPLETED,
    APPROVAL_GATE_REVIEW_REWORK,
    APPROVAL_GATE_SELF_REVIEW_PREVENTED,
    APPROVAL_GATE_TASK_NOT_FOUND,
    APPROVAL_GATE_TASK_UNASSIGNED,
)

if TYPE_CHECKING:
    from synthorg.core.task import Task
    from synthorg.engine.task_engine import TaskEngine
    from synthorg.persistence.protocol import PersistenceBackend

logger = get_logger(__name__)


class ReviewGateService:
    """Handles IN_REVIEW -> COMPLETED/IN_PROGRESS transitions.

    Called by the approval controller when a review-gate approval
    is approved or rejected.  Enforces no-self-review (the decider
    must not be the original executing agent) and records every
    decision to the decisions drop-box.

    Args:
        task_engine: Centralized task engine for status sync and
            task lookup (required for self-review enforcement).
        persistence: Persistence backend -- ``decision_records`` is
            accessed lazily so the backend may be constructed before
            ``persistence.connect()`` is called.
    """

    def __init__(
        self,
        *,
        task_engine: TaskEngine,
        persistence: PersistenceBackend,
    ) -> None:
        self._task_engine = task_engine
        self._persistence = persistence

    async def check_can_decide(
        self,
        *,
        task_id: str,
        decided_by: str,
    ) -> Task:
        """Preflight check: task exists and decider is not the executor.

        Call this BEFORE persisting the approval decision so that a
        rejected preflight never leaves a decided approval row behind.

        Args:
            task_id: The task identifier.
            decided_by: The identity attempting the decision.

        Returns:
            The task (cached so the caller can reuse it for
            ``complete_review`` without re-fetching).

        Raises:
            TaskNotFoundError: If the task cannot be found.
            SelfReviewError: If the decider is the task's original
                executing agent.
        """
        task = await self._task_engine.get_task(task_id)
        if task is None:
            logger.warning(
                APPROVAL_GATE_TASK_NOT_FOUND,
                task_id=task_id,
                decided_by=decided_by,
            )
            msg = f"Task {task_id!r} not found during review gate preflight"
            raise TaskNotFoundError(msg)

        self._check_self_review(task, decided_by=decided_by)
        return task

    async def complete_review(
        self,
        *,
        task_id: str,
        requested_by: str,
        approved: bool,
        decided_by: str,
        reason: str | None = None,
    ) -> None:
        """Transition a task out of IN_REVIEW and record the decision.

        On approve: IN_REVIEW -> COMPLETED.
        On reject: IN_REVIEW -> IN_PROGRESS (rework).

        The self-review check runs again here defensively; callers that
        already invoked ``check_can_decide`` will pass through quickly.

        Raises:
            TaskNotFoundError: If the task cannot be found.
            SelfReviewError: If the decider is the task's original
                executing agent.
        """
        task = await self.check_can_decide(task_id=task_id, decided_by=decided_by)

        if approved:
            target = TaskStatus.COMPLETED
            transition_reason = f"Review approved by {decided_by}"
            event = APPROVAL_GATE_REVIEW_COMPLETED
        else:
            target = TaskStatus.IN_PROGRESS
            transition_reason = f"Review rejected by {decided_by}"
            if reason:
                transition_reason += f": {reason}"
            event = APPROVAL_GATE_REVIEW_REWORK

        logger.info(
            event,
            task_id=task_id,
            requested_by=requested_by,
            decided_by=decided_by,
            target_status=target.value,
        )

        await sync_to_task_engine(
            self._task_engine,
            target_status=target,
            task_id=task_id,
            agent_id="review-gate-service",
            reason=transition_reason,
        )

        await self._record_decision(
            task=task,
            decided_by=decided_by,
            approved=approved,
            reason=reason,
        )

    def _check_self_review(self, task: Task, *, decided_by: str) -> None:
        """Raise ``SelfReviewError`` when the decider is the executor.

        If ``task.assigned_to`` is ``None`` the check is skipped and a
        WARNING is logged: a task reaching review without an assignee
        is an anomalous state worth operator attention.
        """
        if task.assigned_to is None:
            logger.warning(
                APPROVAL_GATE_TASK_UNASSIGNED,
                task_id=task.id,
                decided_by=decided_by,
                status=task.status.value,
            )
            return
        if decided_by == task.assigned_to:
            logger.warning(
                APPROVAL_GATE_SELF_REVIEW_PREVENTED,
                task_id=task.id,
                agent_id=decided_by,
            )
            raise SelfReviewError(task_id=task.id, agent_id=decided_by)

    async def _record_decision(
        self,
        *,
        task: Task,
        decided_by: str,
        approved: bool,
        reason: str | None,
    ) -> None:
        """Append a decision record to the drop-box (best-effort).

        Uses ``append_with_next_version`` so version assignment happens
        atomically in SQL -- no TOCTOU race across concurrent reviewers.

        The transition has already happened at this point, so a failed
        append is logged at ERROR (audit integrity is the whole point
        of this drop-box) but does not raise.
        """
        normalized_reason = reason if reason and reason.strip() else None
        decision = DecisionOutcome.APPROVED if approved else DecisionOutcome.REJECTED
        criteria_snapshot = tuple(
            c.description for c in task.acceptance_criteria if c.description.strip()
        )
        try:
            record = await self._persistence.decision_records.append_with_next_version(
                record_id=str(uuid.uuid4()),
                task_id=task.id,
                approval_id=None,
                executing_agent_id=task.assigned_to or "unassigned",
                reviewer_agent_id=decided_by,
                decision=decision,
                reason=normalized_reason,
                criteria_snapshot=criteria_snapshot,
                recorded_at=datetime.now(UTC),
                metadata={},
            )
            logger.info(
                APPROVAL_GATE_DECISION_RECORDED,
                task_id=task.id,
                decision=record.decision.value,
                version=record.version,
            )
        except MemoryError, RecursionError:
            raise
        except Exception as exc:
            logger.exception(
                APPROVAL_GATE_DECISION_RECORD_FAILED,
                task_id=task.id,
                error_type=type(exc).__name__,
                error=str(exc),
            )
