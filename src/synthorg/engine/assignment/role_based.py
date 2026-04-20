"""Role-based (capability-scored) task assignment strategy."""

from typing import TYPE_CHECKING

from synthorg.engine.assignment._shared import (
    STRATEGY_NAME_ROLE_BASED,
    build_subtask_definition,
    score_and_filter_candidates,
)
from synthorg.engine.assignment.models import AssignmentRequest, AssignmentResult
from synthorg.observability import get_logger
from synthorg.observability.events.task_assignment import TASK_ASSIGNMENT_NO_ELIGIBLE

if TYPE_CHECKING:
    from synthorg.engine.routing.scorer import AgentTaskScorer

logger = get_logger(__name__)


class RoleBasedAssignmentStrategy:
    """Assigns a task to the best-scoring agent by capability.

    Uses ``AgentTaskScorer`` to score all available agents and
    selects the highest-scoring one above the minimum threshold.
    """

    __slots__ = ("_scorer",)

    def __init__(self, scorer: AgentTaskScorer) -> None:
        self._scorer = scorer

    @property
    def name(self) -> str:
        """Strategy name identifier."""
        return STRATEGY_NAME_ROLE_BASED

    def assign(self, request: AssignmentRequest) -> AssignmentResult:
        """Score and rank agents, selecting the best match.

        Returns ``selected=None`` when no candidates meet threshold.

        Args:
            request: The assignment request.

        Returns:
            Assignment result with the best-scoring agent.
        """
        subtask = build_subtask_definition(request)
        candidates = score_and_filter_candidates(
            self._scorer,
            request,
            subtask,
        )

        if not candidates:
            logger.warning(
                TASK_ASSIGNMENT_NO_ELIGIBLE,
                task_id=request.task.id,
                strategy=self.name,
                agent_count=len(request.available_agents),
                min_score=request.min_score,
            )
            return AssignmentResult(
                task_id=request.task.id,
                strategy_used=self.name,
                reason=(
                    f"No agents scored above threshold "
                    f"{request.min_score} for task {request.task.id!r}"
                ),
            )

        selected = candidates[0]
        alternatives = tuple(candidates[1:])

        return AssignmentResult(
            task_id=request.task.id,
            strategy_used=self.name,
            selected=selected,
            alternatives=alternatives,
            reason=f"Best match: {selected.agent_identity.name!r} "
            f"(score={selected.score:.2f})",
        )
