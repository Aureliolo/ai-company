"""Delegation service orchestrating hierarchy, authority, and loop prevention."""

from datetime import UTC, datetime
from uuid import uuid4

from ai_company.communication.delegation.authority import (  # noqa: TC001
    AuthorityValidator,
)
from ai_company.communication.delegation.hierarchy import (  # noqa: TC001
    HierarchyResolver,
)
from ai_company.communication.delegation.models import (
    DelegationRecord,
    DelegationRequest,
    DelegationResult,
)
from ai_company.communication.loop_prevention.guard import (  # noqa: TC001
    DelegationGuard,
)
from ai_company.core.agent import AgentIdentity  # noqa: TC001
from ai_company.core.task import Task
from ai_company.observability import get_logger
from ai_company.observability.events.delegation import (
    DELEGATION_CREATED,
    DELEGATION_REQUESTED,
)

logger = get_logger(__name__)


class DelegationService:
    """Orchestrates hierarchical delegation with loop prevention.

    Validates authority, checks loop prevention guards, creates
    sub-tasks, and records audit trail entries. The core logic is
    synchronous (CPU-only); messaging is a separate async concern.

    Args:
        hierarchy: Resolved organizational hierarchy.
        authority_validator: Authority validation logic.
        guard: Loop prevention guard.
    """

    __slots__ = (
        "_audit_trail",
        "_authority_validator",
        "_guard",
        "_hierarchy",
    )

    def __init__(
        self,
        *,
        hierarchy: HierarchyResolver,
        authority_validator: AuthorityValidator,
        guard: DelegationGuard,
    ) -> None:
        self._hierarchy = hierarchy
        self._authority_validator = authority_validator
        self._guard = guard
        self._audit_trail: list[DelegationRecord] = []

    def delegate(
        self,
        request: DelegationRequest,
        delegator: AgentIdentity,
        delegatee: AgentIdentity,
    ) -> DelegationResult:
        """Execute a delegation: authority, loops, sub-task, audit.

        Args:
            request: The delegation request.
            delegator: Identity of the delegating agent.
            delegatee: Identity of the target agent.

        Returns:
            Result indicating success or rejection with reason.
        """
        logger.info(
            DELEGATION_REQUESTED,
            delegator=request.delegator_id,
            delegatee=request.delegatee_id,
            task_id=request.task.id,
        )

        # 1. Authority check
        auth_result = self._authority_validator.validate(delegator, delegatee)
        if not auth_result.allowed:
            return DelegationResult(
                success=False,
                rejection_reason=auth_result.reason,
                blocked_by="authority",
            )

        # 2. Loop prevention checks
        guard_outcome = self._guard.check(
            delegation_chain=request.task.delegation_chain,
            delegator_id=request.delegator_id,
            delegatee_id=request.delegatee_id,
            task_title=request.task.title,
        )
        if not guard_outcome.passed:
            return DelegationResult(
                success=False,
                rejection_reason=guard_outcome.message,
                blocked_by=guard_outcome.mechanism,
            )

        # 3. Create sub-task
        sub_task = self._create_sub_task(request)

        # 4. Record in guard and audit trail
        self._guard.record_delegation(
            request.delegator_id,
            request.delegatee_id,
            request.task.title,
        )
        record = DelegationRecord(
            delegation_id=str(uuid4()),
            delegator_id=request.delegator_id,
            delegatee_id=request.delegatee_id,
            original_task_id=request.task.id,
            delegated_task_id=sub_task.id,
            timestamp=datetime.now(UTC),
            refinement=request.refinement,
        )
        self._audit_trail.append(record)

        logger.info(
            DELEGATION_CREATED,
            delegator=request.delegator_id,
            delegatee=request.delegatee_id,
            original_task_id=request.task.id,
            delegated_task_id=sub_task.id,
        )

        return DelegationResult(
            success=True,
            delegated_task=sub_task,
        )

    def _create_sub_task(self, request: DelegationRequest) -> Task:
        """Create a new sub-task from a delegation request.

        The sub-task inherits the original task's properties but gets
        a new ID, parent reference, extended delegation chain, and
        CREATED status.

        Args:
            request: The delegation request.

        Returns:
            New Task with delegation metadata.
        """
        original = request.task
        new_chain = (*original.delegation_chain, request.delegator_id)
        description = original.description
        if request.refinement:
            description = (
                f"{original.description}\n\nDelegation context: {request.refinement}"
            )

        return Task(
            id=f"del-{uuid4().hex[:12]}",
            title=original.title,
            description=description,
            type=original.type,
            priority=original.priority,
            project=original.project,
            created_by=request.delegator_id,
            parent_task_id=original.id,
            delegation_chain=new_chain,
            estimated_complexity=original.estimated_complexity,
            budget_limit=original.budget_limit,
            deadline=original.deadline,
        )

    def get_audit_trail(self) -> tuple[DelegationRecord, ...]:
        """Return all delegation audit records.

        Returns:
            Tuple of delegation records in chronological order.
        """
        return tuple(self._audit_trail)

    def get_supervisor_of(self, agent_name: str) -> str | None:
        """Expose hierarchy lookup for escalation callers.

        Args:
            agent_name: Agent name to look up.

        Returns:
            Supervisor name or None if at the top.
        """
        return self._hierarchy.get_supervisor(agent_name)
