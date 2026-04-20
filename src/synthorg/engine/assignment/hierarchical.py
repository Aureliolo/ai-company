"""Hierarchical (delegation-aware) task assignment strategy."""

from typing import TYPE_CHECKING

from synthorg.engine.assignment._shared import (
    STRATEGY_NAME_HIERARCHICAL,
    build_subtask_definition,
    score_and_filter_candidates,
)
from synthorg.engine.assignment.models import AssignmentRequest, AssignmentResult
from synthorg.observability import get_logger
from synthorg.observability.events.task_assignment import (
    TASK_ASSIGNMENT_DELEGATOR_RESOLVED,
    TASK_ASSIGNMENT_HIERARCHICAL_DELEGATED,
    TASK_ASSIGNMENT_HIERARCHY_TRANSITIVE,
    TASK_ASSIGNMENT_NO_ELIGIBLE,
)

if TYPE_CHECKING:
    from synthorg.communication.delegation.hierarchy import HierarchyResolver
    from synthorg.core.agent import AgentIdentity
    from synthorg.engine.routing.scorer import AgentTaskScorer

logger = get_logger(__name__)


class HierarchicalAssignmentStrategy:
    """Assigns a task to a subordinate of the delegator.

    Identifies the delegator from ``task.delegation_chain[-1]``
    (the deepest in the root-first chain) or ``task.created_by`` as
    fallback, then filters the agent pool to the delegator's
    direct reports.  Falls back to transitive subordinates if
    no direct report matches.
    """

    __slots__ = ("_hierarchy", "_scorer")

    def __init__(
        self,
        scorer: AgentTaskScorer,
        hierarchy: HierarchyResolver,
    ) -> None:
        self._scorer = scorer
        self._hierarchy = hierarchy

    @property
    def name(self) -> str:
        """Strategy name identifier."""
        return STRATEGY_NAME_HIERARCHICAL

    def _resolve_delegator(self, request: AssignmentRequest) -> str:
        """Determine the delegator from the task.

        Uses ``delegation_chain[-1]`` if non-empty, else ``created_by``.

        Args:
            request: The assignment request.

        Returns:
            Delegator agent name.
        """
        task = request.task
        if task.delegation_chain:
            delegator = task.delegation_chain[-1]
            logger.debug(
                TASK_ASSIGNMENT_DELEGATOR_RESOLVED,
                task_id=task.id,
                delegator=delegator,
                source="delegation_chain",
            )
            return delegator
        logger.debug(
            TASK_ASSIGNMENT_DELEGATOR_RESOLVED,
            task_id=task.id,
            delegator=task.created_by,
            source="created_by",
        )
        return task.created_by

    def _filter_by_hierarchy(
        self,
        request: AssignmentRequest,
        delegator: str,
    ) -> tuple[AgentIdentity, ...]:
        """Filter available agents to subordinates of the delegator.

        Tries direct reports first, then transitive subordinates.

        Args:
            request: The assignment request.
            delegator: Delegator agent name.

        Returns:
            Filtered tuple of agents that are subordinates.
        """
        direct_reports = set(self._hierarchy.get_direct_reports(delegator))

        direct = tuple(a for a in request.available_agents if a.name in direct_reports)
        if direct:
            return direct

        available_names = tuple(a.name for a in request.available_agents)
        logger.debug(
            TASK_ASSIGNMENT_HIERARCHY_TRANSITIVE,
            delegator=delegator,
            direct_reports=tuple(sorted(direct_reports)),
            available_agents=available_names,
        )
        return tuple(
            a
            for a in request.available_agents
            if self._hierarchy.is_subordinate(delegator, a.name)
        )

    def _is_known_delegator(self, delegator: str) -> bool:
        """Check if the delegator exists in the hierarchy.

        An agent is "known" if it has direct reports or a supervisor.

        Args:
            delegator: Delegator agent name.

        Returns:
            True if the delegator is part of the hierarchy.
        """
        has_reports = bool(self._hierarchy.get_direct_reports(delegator))
        has_supervisor = self._hierarchy.get_supervisor(delegator) is not None
        return has_reports or has_supervisor

    def _score_subordinates(
        self,
        request: AssignmentRequest,
        delegator: str,
        subordinates: tuple[AgentIdentity, ...],
    ) -> AssignmentResult:
        """Score subordinates and select the best match.

        Args:
            request: The original assignment request.
            delegator: Delegator agent name.
            subordinates: Filtered subordinate agents.

        Returns:
            Assignment result with best-scoring subordinate.
        """
        filtered_request = AssignmentRequest(
            task=request.task,
            available_agents=subordinates,
            workloads=request.workloads,
            min_score=request.min_score,
            required_skills=request.required_skills,
            required_role=request.required_role,
            max_concurrent_tasks=request.max_concurrent_tasks,
        )

        subtask = build_subtask_definition(filtered_request)
        candidates = score_and_filter_candidates(
            self._scorer,
            filtered_request,
            subtask,
        )

        if not candidates:
            logger.warning(
                TASK_ASSIGNMENT_NO_ELIGIBLE,
                task_id=request.task.id,
                strategy=self.name,
                delegator=delegator,
                agent_count=len(subordinates),
                min_score=request.min_score,
            )
            return AssignmentResult(
                task_id=request.task.id,
                strategy_used=self.name,
                reason=(
                    f"No subordinates of {delegator!r} scored above "
                    f"threshold {request.min_score} "
                    f"for task {request.task.id!r}"
                ),
            )

        selected = candidates[0]
        alternatives = tuple(candidates[1:])

        logger.debug(
            TASK_ASSIGNMENT_HIERARCHICAL_DELEGATED,
            task_id=request.task.id,
            delegator=delegator,
            agent_name=selected.agent_identity.name,
            score=selected.score,
        )

        return AssignmentResult(
            task_id=request.task.id,
            strategy_used=self.name,
            selected=selected,
            alternatives=alternatives,
            reason=f"Delegated from {delegator!r} to "
            f"{selected.agent_identity.name!r} "
            f"(score={selected.score:.2f})",
        )

    def assign(self, request: AssignmentRequest) -> AssignmentResult:
        """Assign to the best-scoring subordinate of the delegator.

        Returns ``selected=None`` when no candidates meet threshold.

        Args:
            request: The assignment request.

        Returns:
            Assignment result with the best subordinate.
        """
        delegator = self._resolve_delegator(request)

        if not self._is_known_delegator(delegator):
            logger.warning(
                TASK_ASSIGNMENT_NO_ELIGIBLE,
                task_id=request.task.id,
                strategy=self.name,
                delegator=delegator,
                reason="unknown_delegator",
            )
            return AssignmentResult(
                task_id=request.task.id,
                strategy_used=self.name,
                reason=f"Delegator {delegator!r} not found in hierarchy",
            )

        subordinates = self._filter_by_hierarchy(request, delegator)

        if not subordinates:
            logger.warning(
                TASK_ASSIGNMENT_NO_ELIGIBLE,
                task_id=request.task.id,
                strategy=self.name,
                delegator=delegator,
                reason="no_subordinates",
            )
            return AssignmentResult(
                task_id=request.task.id,
                strategy_used=self.name,
                reason=(
                    f"No subordinates of {delegator!r} found "
                    f"in available agents for task {request.task.id!r}"
                ),
            )

        return self._score_subordinates(request, delegator, subordinates)
