"""Review gate service -- IN_REVIEW task transitions on approval decisions.

Handles the post-execution review gate: when a human approves or rejects
a completed task, this service transitions it from IN_REVIEW to COMPLETED
(approve) or IN_PROGRESS (reject/rework) via the TaskEngine.
"""

from typing import TYPE_CHECKING

from synthorg.core.enums import TaskStatus
from synthorg.engine.task_sync import sync_to_task_engine
from synthorg.observability import get_logger
from synthorg.observability.events.approval_gate import (
    APPROVAL_GATE_REVIEW_COMPLETED,
    APPROVAL_GATE_REVIEW_REWORK,
)

if TYPE_CHECKING:
    from synthorg.engine.task_engine import TaskEngine

logger = get_logger(__name__)


class ReviewGateService:
    """Handles IN_REVIEW -> COMPLETED/IN_PROGRESS transitions.

    Called by the approval controller when a review-gate approval
    is approved or rejected.  Delegates to ``sync_to_task_engine``
    for best-effort TaskEngine sync.

    Args:
        task_engine: Optional centralized task engine for status sync.
    """

    def __init__(self, *, task_engine: TaskEngine | None = None) -> None:
        self._task_engine = task_engine

    async def complete_review(
        self,
        *,
        task_id: str,
        agent_id: str,
        approved: bool,
        decided_by: str,
        reason: str | None = None,
    ) -> None:
        """Transition a task out of IN_REVIEW.

        On approve: IN_REVIEW -> COMPLETED.
        On reject: IN_REVIEW -> IN_PROGRESS (rework).

        Args:
            task_id: The task identifier.
            agent_id: The agent that executed the task.
            approved: Whether the review was approved.
            decided_by: Who made the decision.
            reason: Optional reason for the decision.
        """
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
            agent_id=agent_id,
            decided_by=decided_by,
            target_status=target.value,
        )

        await sync_to_task_engine(
            self._task_engine,
            target_status=target,
            task_id=task_id,
            agent_id=agent_id,
            reason=transition_reason,
        )
