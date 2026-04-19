"""Auction-based task assignment strategy."""

from typing import TYPE_CHECKING

from synthorg.engine.assignment._shared import (
    STRATEGY_NAME_AUCTION,
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
    TASK_ASSIGNMENT_AUCTION_BID,
    TASK_ASSIGNMENT_AUCTION_WON,
    TASK_ASSIGNMENT_CAPABILITY_FALLBACK,
    TASK_ASSIGNMENT_NO_ELIGIBLE,
)

if TYPE_CHECKING:
    from synthorg.engine.routing.scorer import AgentTaskScorer

logger = get_logger(__name__)


class AuctionAssignmentStrategy:
    """Assigns a task via simulated auction bidding.

    Each agent's bid is ``capability_score * availability_factor``,
    where ``availability_factor = 1.0 / (1.0 + active_task_count)``.
    The highest bidder wins.  When no workload data is provided,
    all availability factors default to 1.0, making bids equal
    to raw capability scores.
    """

    __slots__ = ("_scorer",)

    def __init__(self, scorer: AgentTaskScorer) -> None:
        self._scorer = scorer

    @property
    def name(self) -> str:
        """Strategy name identifier."""
        return STRATEGY_NAME_AUCTION

    def assign(self, request: AssignmentRequest) -> AssignmentResult:
        """Run a simulated auction and select the highest bidder.

        Returns ``selected=None`` when no candidates meet threshold.

        Args:
            request: The assignment request.

        Returns:
            Assignment result with the highest-bidding agent.
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

        workload_map: dict[str, int] = {
            w.agent_id: w.active_task_count for w in request.workloads
        }
        candidate_ids = {str(c.agent_identity.id) for c in candidates}
        has_complete_data = bool(workload_map) and candidate_ids <= workload_map.keys()

        if not has_complete_data and workload_map:
            logger.warning(
                TASK_ASSIGNMENT_CAPABILITY_FALLBACK,
                task_id=request.task.id,
                strategy=self.name,
                partial_data=True,
            )

        bids: list[tuple[AssignmentCandidate, float]] = []
        for candidate in candidates:
            if has_complete_data:
                active_tasks = workload_map[str(candidate.agent_identity.id)]
                availability = 1.0 / (1.0 + active_tasks)
            else:
                availability = 1.0
            bid = candidate.score * availability

            logger.debug(
                TASK_ASSIGNMENT_AUCTION_BID,
                task_id=request.task.id,
                agent_name=candidate.agent_identity.name,
                score=candidate.score,
                availability=availability,
                bid=bid,
            )

            bids.append((candidate, bid))

        bids.sort(key=lambda x: (x[1], x[0].score), reverse=True)

        selected = bids[0][0]
        alternatives = tuple(b[0] for b in bids[1:])

        logger.debug(
            TASK_ASSIGNMENT_AUCTION_WON,
            task_id=request.task.id,
            agent_name=selected.agent_identity.name,
            winning_bid=bids[0][1],
        )

        return AssignmentResult(
            task_id=request.task.id,
            strategy_used=self.name,
            selected=selected,
            alternatives=alternatives,
            reason=f"Auction winner: {selected.agent_identity.name!r} "
            f"(bid={bids[0][1]:.4f})",
        )
