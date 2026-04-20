"""Cost-optimized task assignment strategy."""

from typing import TYPE_CHECKING

from synthorg.engine.assignment._shared import (
    STRATEGY_NAME_COST_OPTIMIZED,
    build_subtask_definition,
    score_and_filter_candidates,
)
from synthorg.engine.assignment.models import AssignmentRequest, AssignmentResult
from synthorg.observability import get_logger
from synthorg.observability.events.task_assignment import (
    TASK_ASSIGNMENT_CAPABILITY_FALLBACK,
    TASK_ASSIGNMENT_COST_OPTIMIZED,
    TASK_ASSIGNMENT_NO_ELIGIBLE,
)

if TYPE_CHECKING:
    from synthorg.engine.routing.scorer import AgentTaskScorer

logger = get_logger(__name__)


class CostOptimizedAssignmentStrategy:
    """Assigns a task to the cheapest eligible agent.

    Scores agents like ``RoleBasedAssignmentStrategy``, then
    sorts by ``total_cost`` (ascending) with score as
    tiebreaker (descending).  Falls back to score-based
    ranking when cost data is absent or incomplete.
    """

    __slots__ = ("_scorer",)

    def __init__(self, scorer: AgentTaskScorer) -> None:
        self._scorer = scorer

    @property
    def name(self) -> str:
        """Strategy name identifier."""
        return STRATEGY_NAME_COST_OPTIMIZED

    def assign(self, request: AssignmentRequest) -> AssignmentResult:
        """Score, sort by cost, and select the cheapest eligible agent.

        Returns ``selected=None`` when no candidates meet threshold.

        Args:
            request: The assignment request.

        Returns:
            Assignment result with the cheapest eligible agent.
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

        cost_map: dict[str, float] = {
            w.agent_id: w.total_cost for w in request.workloads
        }
        candidate_ids = {str(c.agent_identity.id) for c in candidates}
        has_complete_data = bool(cost_map) and candidate_ids <= cost_map.keys()

        if has_complete_data:
            candidates = sorted(
                candidates,
                key=lambda c: (
                    cost_map[str(c.agent_identity.id)],
                    -c.score,
                ),
            )
            logger.debug(
                TASK_ASSIGNMENT_COST_OPTIMIZED,
                task_id=request.task.id,
                agent_name=candidates[0].agent_identity.name,
                total_cost=cost_map[str(candidates[0].agent_identity.id)],
            )
        else:
            logger.warning(
                TASK_ASSIGNMENT_CAPABILITY_FALLBACK,
                task_id=request.task.id,
                strategy=self.name,
                partial_data=bool(cost_map),
            )

        selected = candidates[0]
        alternatives = tuple(candidates[1:])

        reason = (
            f"Cheapest: {selected.agent_identity.name!r} (score={selected.score:.2f})"
            if has_complete_data
            else f"Best match (insufficient cost data): "
            f"{selected.agent_identity.name!r} "
            f"(score={selected.score:.2f})"
        )

        return AssignmentResult(
            task_id=request.task.id,
            strategy_used=self.name,
            selected=selected,
            alternatives=alternatives,
            reason=reason,
        )
