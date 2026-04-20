"""Load-balanced task assignment strategy."""

from typing import TYPE_CHECKING

from synthorg.engine.assignment._shared import (
    STRATEGY_NAME_LOAD_BALANCED,
    build_subtask_definition,
    score_and_filter_candidates,
)
from synthorg.engine.assignment.models import (
    AssignmentCandidate,
    AssignmentRequest,
    AssignmentResult,
)
from synthorg.observability import get_logger
from synthorg.observability.events.task_assignment import (
    TASK_ASSIGNMENT_CAPABILITY_FALLBACK,
    TASK_ASSIGNMENT_NO_ELIGIBLE,
    TASK_ASSIGNMENT_WORKLOAD_BALANCED,
)

if TYPE_CHECKING:
    from synthorg.engine.routing.scorer import AgentTaskScorer

logger = get_logger(__name__)


class LoadBalancedAssignmentStrategy:
    """Assigns a task to the least-loaded eligible agent.

    Scores agents like ``RoleBasedAssignmentStrategy``, then
    sorts by workload (ascending) with score as tiebreaker
    (descending). Falls back to score-based ranking when
    workload data is absent or incomplete.
    """

    __slots__ = ("_scorer",)

    def __init__(self, scorer: AgentTaskScorer) -> None:
        self._scorer = scorer

    @property
    def name(self) -> str:
        """Strategy name identifier."""
        return STRATEGY_NAME_LOAD_BALANCED

    def assign(self, request: AssignmentRequest) -> AssignmentResult:
        """Score, filter by workload, and select the least-loaded agent."""
        subtask = build_subtask_definition(request)
        candidates = score_and_filter_candidates(self._scorer, request, subtask)
        if not candidates:
            return self._no_eligible_result(request)

        ranked, has_complete_data = self._rank_candidates_by_workload(
            request,
            candidates,
        )
        return self._build_result(request, ranked, has_complete_data=has_complete_data)

    def _no_eligible_result(self, request: AssignmentRequest) -> AssignmentResult:
        """Log and return an empty result when no candidates scored."""
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

    def _rank_candidates_by_workload(
        self,
        request: AssignmentRequest,
        candidates: list[AssignmentCandidate],
    ) -> tuple[list[AssignmentCandidate], bool]:
        """Sort candidates by workload + score; return the used-workload flag."""
        workload_map: dict[str, int] = {
            w.agent_id: w.active_task_count for w in request.workloads
        }
        candidate_ids = {str(c.agent_identity.id) for c in candidates}
        has_complete_data = bool(workload_map) and candidate_ids <= workload_map.keys()
        if has_complete_data:
            ranked = sorted(
                candidates,
                key=lambda c: (
                    workload_map[str(c.agent_identity.id)],
                    -c.score,
                ),
            )
            logger.debug(
                TASK_ASSIGNMENT_WORKLOAD_BALANCED,
                task_id=request.task.id,
                agent_name=ranked[0].agent_identity.name,
                workload=workload_map[str(ranked[0].agent_identity.id)],
            )
            return ranked, True
        logger.warning(
            TASK_ASSIGNMENT_CAPABILITY_FALLBACK,
            task_id=request.task.id,
            strategy=self.name,
            partial_data=bool(workload_map),
        )
        return candidates, False

    def _build_result(
        self,
        request: AssignmentRequest,
        ranked: list[AssignmentCandidate],
        *,
        has_complete_data: bool,
    ) -> AssignmentResult:
        """Build the final ``AssignmentResult`` from ranked candidates."""
        selected = ranked[0]
        # Alternatives are score-ranked (not workload-ranked) so the
        # shared ``AssignmentResult`` contract stays consistent for
        # callers that treat them as a generic fallback list.
        alternatives = tuple(
            sorted(ranked[1:], key=lambda c: c.score, reverse=True),
        )
        reason = (
            f"Least loaded: {selected.agent_identity.name!r} "
            f"(score={selected.score:.2f})"
            if has_complete_data
            else f"Best match (insufficient workload data): "
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
