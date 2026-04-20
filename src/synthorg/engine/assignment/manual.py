"""Manual task assignment strategy.

Assigns a task to its pre-designated agent identified by
``task.assigned_to``. The field may carry either the agent's UUID
(canonical, as populated by API callers) or the agent's declarative
``name`` (as populated by workflow AGENT_ASSIGNMENT nodes); both
forms are accepted.
"""

from typing import TYPE_CHECKING

from synthorg.core.enums import AgentStatus
from synthorg.engine.assignment._shared import STRATEGY_NAME_MANUAL
from synthorg.engine.assignment.models import (
    AssignmentCandidate,
    AssignmentRequest,
    AssignmentResult,
)
from synthorg.engine.errors import NoEligibleAgentError, TaskAssignmentError
from synthorg.observability import get_logger
from synthorg.observability.events.task_assignment import (
    TASK_ASSIGNMENT_FAILED,
    TASK_ASSIGNMENT_MANUAL_VALIDATED,
)

if TYPE_CHECKING:
    from synthorg.core.agent import AgentIdentity

logger = get_logger(__name__)


class ManualAssignmentStrategy:
    """Assigns a task to its pre-designated agent.

    Requires ``task.assigned_to`` to be set. Validates that
    the designated agent exists in the pool and is ACTIVE.
    """

    __slots__ = ()

    @property
    def name(self) -> str:
        """Strategy name identifier."""
        return STRATEGY_NAME_MANUAL

    def _find_designated_agent(
        self,
        request: AssignmentRequest,
    ) -> AgentIdentity:
        """Find and validate the designated agent in the pool.

        Args:
            request: The assignment request.

        Returns:
            The validated, ACTIVE designated agent.

        Raises:
            TaskAssignmentError: If ``task.assigned_to`` is None.
            NoEligibleAgentError: If the designated agent is not in
                the pool or is not ACTIVE.
        """
        task = request.task
        if task.assigned_to is None:
            msg = (
                f"Manual assignment requires task.assigned_to to be set "
                f"for task {task.id!r}"
            )
            logger.warning(
                TASK_ASSIGNMENT_FAILED,
                task_id=task.id,
                strategy=self.name,
                error=msg,
            )
            raise TaskAssignmentError(msg)

        # Accept either the agent's UUID (API-authored tasks) or the agent's
        # ``name`` (workflow AGENT_ASSIGNMENT nodes store the declarative
        # name rather than the opaque UUID). UUID matching is preferred when
        # present; name matching is the fallback for workflow-sourced tasks.
        agent: AgentIdentity | None = None
        for available in request.available_agents:
            if str(available.id) == task.assigned_to:
                agent = available
                break
        if agent is None:
            for available in request.available_agents:
                if available.name == task.assigned_to:
                    agent = available
                    break

        if agent is None:
            msg = (
                f"Designated agent {task.assigned_to!r} not found "
                f"in available agents for task {task.id!r}"
            )
            logger.warning(
                TASK_ASSIGNMENT_FAILED,
                task_id=task.id,
                strategy=self.name,
                designated_agent=task.assigned_to,
                error=msg,
            )
            raise NoEligibleAgentError(msg)

        if agent.status != AgentStatus.ACTIVE:
            msg = (
                f"Designated agent {agent.name!r} has status "
                f"{agent.status.value!r}, expected 'active' "
                f"for task {task.id!r}"
            )
            logger.warning(
                TASK_ASSIGNMENT_FAILED,
                task_id=task.id,
                strategy=self.name,
                agent_name=agent.name,
                agent_status=agent.status.value,
                error=msg,
            )
            raise NoEligibleAgentError(msg)

        return agent

    def assign(self, request: AssignmentRequest) -> AssignmentResult:
        """Assign to the agent specified by ``task.assigned_to``.

        Args:
            request: The assignment request.

        Returns:
            Assignment result with the designated agent.

        Raises:
            TaskAssignmentError: If ``task.assigned_to`` is None.
            NoEligibleAgentError: If the designated agent is not in
                the pool or is not ACTIVE.
        """
        agent = self._find_designated_agent(request)
        task = request.task

        candidate = AssignmentCandidate(
            agent_identity=agent,
            score=1.0,
            matched_skills=(),
            reason="Manually assigned",
        )

        logger.debug(
            TASK_ASSIGNMENT_MANUAL_VALIDATED,
            task_id=task.id,
            agent_name=agent.name,
        )

        return AssignmentResult(
            task_id=task.id,
            strategy_used=self.name,
            selected=candidate,
            reason=f"Manually assigned to {agent.name!r}",
        )
