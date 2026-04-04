"""Review gate service -- IN_REVIEW task transitions on approval decisions.

Handles the post-execution review gate: when a human approves or rejects
a completed task, this service transitions it from IN_REVIEW to COMPLETED
(approve) or IN_PROGRESS (reject/rework) via the TaskEngine.

Enforces structural no-self-review at the approval gate boundary:
the decider must not be the same agent as the task's original executor.
Every decision is appended to the auditable decisions drop-box.
"""

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from synthorg.core.enums import DecisionOutcome, TaskStatus
from synthorg.engine.decisions import DecisionRecord
from synthorg.engine.errors import SelfReviewError, TaskNotFoundError
from synthorg.engine.task_sync import sync_to_task_engine
from synthorg.observability import get_logger
from synthorg.observability.events.approval_gate import (
    APPROVAL_GATE_DECISION_RECORD_FAILED,
    APPROVAL_GATE_DECISION_RECORDED,
    APPROVAL_GATE_REVIEW_COMPLETED,
    APPROVAL_GATE_REVIEW_REWORK,
    APPROVAL_GATE_SELF_REVIEW_PREVENTED,
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

        Args:
            task_id: The task identifier.
            requested_by: Identity requesting the transition (the
                reviewer, not the original executing agent).
            approved: Whether the review was approved.
            decided_by: Who made the decision.
            reason: Optional reason for the decision.

        Raises:
            TaskNotFoundError: If the task cannot be found.
            SelfReviewError: If the decider is the task's original
                executing agent.
        """
        task = await self._task_engine.get_task(task_id)
        if task is None:
            msg = f"Task {task_id!r} not found during review gate transition"
            raise TaskNotFoundError(msg)

        self._check_self_review(task, decided_by=decided_by)

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

        If ``task.assigned_to`` is ``None`` the check is skipped (no
        executor to enforce against).
        """
        if task.assigned_to is None:
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

        The transition has already happened at this point, so a failed
        append is logged at WARNING but does not raise.
        """
        try:
            decision_repo = self._persistence.decision_records
            existing = await decision_repo.list_by_task(task.id)
            record = DecisionRecord(
                id=str(uuid.uuid4()),
                task_id=task.id,
                executing_agent_id=task.assigned_to or "unassigned",
                reviewer_agent_id=decided_by,
                decision=(
                    DecisionOutcome.APPROVED if approved else DecisionOutcome.REJECTED
                ),
                reason=reason,
                criteria_snapshot=tuple(
                    c.description for c in task.acceptance_criteria
                ),
                recorded_at=datetime.now(UTC),
                version=len(existing) + 1,
                metadata={},
            )
            await decision_repo.append(record)
            logger.info(
                APPROVAL_GATE_DECISION_RECORDED,
                task_id=task.id,
                decision=record.decision.value,
                version=record.version,
            )
        except MemoryError, RecursionError:
            raise
        except Exception:
            logger.warning(
                APPROVAL_GATE_DECISION_RECORD_FAILED,
                task_id=task.id,
                error="Failed to append decision record (non-fatal)",
                exc_info=True,
            )
