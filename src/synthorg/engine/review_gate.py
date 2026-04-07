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
from synthorg.observability.events.versioning import VERSION_FETCH_FAILED
from synthorg.persistence.errors import DuplicateRecordError, QueryError

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
    decision to the decisions drop-box (best effort).

    Args:
        task_engine: Centralized task engine for status sync and
            task lookup (required for self-review enforcement).
        persistence: Optional persistence backend -- ``decision_records``
            is accessed lazily so the backend may be constructed before
            ``persistence.connect()`` is called.  When ``None``, the
            preflight and state-transition paths still run (they only
            need ``task_engine``); decision recording degrades to a
            WARNING-level no-op so the self-review / missing-task
            fail-fast guarantee still holds in backends that do not
            have a persistence layer wired up.
    """

    def __init__(
        self,
        *,
        task_engine: TaskEngine,
        persistence: PersistenceBackend | None = None,
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
            The validated ``Task`` fetched from the engine.  Returned
            for callers that want to inspect task metadata (status,
            assignee) right after the preflight; ``complete_review``
            independently re-fetches the task as defense-in-depth.

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

    async def complete_review(  # noqa: PLR0913
        self,
        *,
        task_id: str,
        requested_by: str,
        approved: bool,
        decided_by: str,
        reason: str | None = None,
        approval_id: str | None = None,
    ) -> None:
        """Transition a task out of IN_REVIEW and record the decision.

        On approve: IN_REVIEW -> COMPLETED.
        On reject: IN_REVIEW -> IN_PROGRESS (rework).

        The self-review check runs a second time here as defense in
        depth.  This is a full DB round-trip through the task engine,
        not a cached pass-through -- the service intentionally does
        not trust that the caller ran the preflight, because the
        preflight is an HTTP-layer optimization and this method is
        the authoritative boundary.

        Args:
            task_id: The task under review.
            requested_by: Agent that requested the review (for logging).
            approved: True for approve, False for reject/rework.
            decided_by: Agent that made the decision.
            reason: Optional rationale, required-free text.
            approval_id: Optional foreign key to the approval item that
                triggered this decision -- persisted on the
                ``DecisionRecord`` for cross-referencing audit trails.

        The ``DecisionRecord`` will include a ``charter_version`` key in
        its metadata when the executing agent has a versioned identity on
        record.  If the version lookup fails with a ``QueryError``, the
        metadata will contain ``{"charter_version_lookup_failed": True}``
        instead, so the failure is surfaced without blocking the decision.

        Raises:
            TaskNotFoundError: If the task cannot be found.
            SelfReviewError: If the decider is the task's original
                executing agent.
        """
        task = await self.check_can_decide(task_id=task_id, decided_by=decided_by)

        # Normalize the reason once at the service boundary: empty or
        # whitespace-only strings collapse to None so the task
        # transition history and DecisionRecord.reason both carry the
        # same canonical value.  ``_record_decision`` previously
        # re-normalized, which allowed the transition reason and the
        # audit record to drift (e.g. "Review rejected by bob:   ").
        normalized_reason = reason.strip() if reason and reason.strip() else None

        if approved:
            target = TaskStatus.COMPLETED
            transition_reason = f"Review approved by {decided_by}"
            event = APPROVAL_GATE_REVIEW_COMPLETED
        else:
            target = TaskStatus.IN_PROGRESS
            transition_reason = f"Review rejected by {decided_by}"
            if normalized_reason is not None:
                transition_reason += f": {normalized_reason}"
            event = APPROVAL_GATE_REVIEW_REWORK

        await sync_to_task_engine(
            self._task_engine,
            target_status=target,
            task_id=task_id,
            agent_id="review-gate-service",
            reason=transition_reason,
        )

        # Log the state transition AFTER sync_to_task_engine succeeds so
        # audit logs reflect actual transitions, not intended ones.
        logger.info(
            event,
            task_id=task_id,
            requested_by=requested_by,
            decided_by=decided_by,
            target_status=target.value,
        )

        await self._record_decision(
            task=task,
            decided_by=decided_by,
            approved=approved,
            reason=normalized_reason,
            approval_id=approval_id,
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
        approval_id: str | None,
    ) -> None:
        """Append a decision record to the drop-box (best-effort).

        Uses ``append_with_next_version`` so version assignment happens
        atomically in SQL -- no TOCTOU race across concurrent reviewers.

        The transition has already happened at this point, so a failed
        append is logged but does not propagate.  Only ``QueryError``
        and ``DuplicateRecordError`` are non-fatal; programming errors
        propagate loudly so schema drift surfaces in dev/CI.
        """
        if self._persistence is None:
            logger.warning(
                APPROVAL_GATE_DECISION_RECORD_FAILED,
                task_id=task.id,
                decided_by=decided_by,
                approved=approved,
                error_type="NoPersistence",
                error=(
                    "Decision recording skipped: no persistence backend "
                    "configured on ReviewGateService"
                ),
            )
            return

        if task.assigned_to is None:
            logger.error(
                APPROVAL_GATE_DECISION_RECORD_FAILED,
                task_id=task.id,
                decided_by=decided_by,
                approved=approved,
                error_type="UnassignedExecutor",
                error=(
                    "Cannot record decision: task reached review gate "
                    "without an assigned executor"
                ),
            )
            return

        decision = DecisionOutcome.APPROVED if approved else DecisionOutcome.REJECTED
        criteria = self._dedupe_criteria(task)
        executor = task.assigned_to
        metadata = await self._fetch_charter_metadata(executor)
        await self._append_decision(
            task_id=task.id,
            executing_agent_id=executor,
            decided_by=decided_by,
            approved=approved,
            approval_id=approval_id,
            decision=decision,
            reason=reason,
            criteria_snapshot=criteria,
            metadata=metadata,
        )

    @staticmethod
    def _dedupe_criteria(task: Task) -> tuple[str, ...]:
        """Dedupe acceptance criteria descriptions preserving order.

        ``DecisionRecord.criteria_snapshot`` rejects duplicates via
        its unique-strings validator; without deduping a task with
        repeated criteria would raise ``ValidationError``.
        """
        seen: set[str] = set()
        result: list[str] = []
        for c in task.acceptance_criteria:
            stripped = c.description.strip()
            if stripped and stripped not in seen:
                seen.add(stripped)
                result.append(stripped)
        return tuple(result)

    async def _fetch_charter_metadata(
        self,
        agent_id: str,
    ) -> dict[str, object] | None:
        """Look up the latest charter version for decision metadata.

        Returns a metadata dict on success, a failure-flag dict on
        ``QueryError``, or ``None`` if no version exists.
        """
        persistence = self._persistence
        assert persistence is not None  # noqa: S101  # caller checks
        try:
            latest = await persistence.identity_versions.get_latest_version(
                agent_id,
            )
        except QueryError as exc:
            logger.warning(
                VERSION_FETCH_FAILED,
                entity_id=agent_id,
                context="charter_version_lookup",
                error=str(exc),
                error_type=type(exc).__name__,
            )
            return {"charter_version_lookup_failed": True}
        if latest is None:
            return None
        return {
            "charter_version": {
                "agent_id": latest.entity_id,
                "version": latest.version,
                "content_hash": latest.content_hash,
            }
        }

    async def _append_decision(  # noqa: PLR0913
        self,
        *,
        task_id: str,
        executing_agent_id: str,
        decided_by: str,
        approved: bool,
        approval_id: str | None,
        decision: DecisionOutcome,
        reason: str | None,
        criteria_snapshot: tuple[str, ...],
        metadata: dict[str, object] | None,
    ) -> None:
        """Append the decision record (best-effort, non-fatal on persistence errors)."""
        persistence = self._persistence
        assert persistence is not None  # noqa: S101  # caller checks
        try:
            record = await persistence.decision_records.append_with_next_version(
                record_id=str(uuid.uuid4()),
                task_id=task_id,
                approval_id=approval_id,
                executing_agent_id=executing_agent_id,
                reviewer_agent_id=decided_by,
                decision=decision,
                reason=reason,
                criteria_snapshot=criteria_snapshot,
                recorded_at=datetime.now(UTC),
                metadata=metadata,
            )
            logger.info(
                APPROVAL_GATE_DECISION_RECORDED,
                task_id=task_id,
                decision=record.decision.value,
                version=record.version,
            )
        except (QueryError, DuplicateRecordError) as exc:
            logger.exception(
                APPROVAL_GATE_DECISION_RECORD_FAILED,
                task_id=task_id,
                decided_by=decided_by,
                approved=approved,
                error_type=type(exc).__name__,
                error=str(exc),
            )
