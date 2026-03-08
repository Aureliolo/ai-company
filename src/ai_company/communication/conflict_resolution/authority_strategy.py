"""Authority + dissent log conflict resolution strategy (DESIGN_SPEC §5.6).

Strategy 1: The agent with higher seniority wins.  For same-seniority
agents, hierarchy position decides.  Cross-department conflicts use
the lowest common manager to determine proximity.
"""

from datetime import UTC, datetime
from uuid import uuid4

from ai_company.communication.conflict_resolution.models import (
    Conflict,
    ConflictPosition,
    ConflictResolution,
    ConflictResolutionOutcome,
    DissentRecord,
)
from ai_company.communication.delegation.hierarchy import (  # noqa: TC001
    HierarchyResolver,
)
from ai_company.communication.enums import ConflictResolutionStrategy
from ai_company.communication.errors import ConflictHierarchyError
from ai_company.core.enums import compare_seniority
from ai_company.observability import get_logger
from ai_company.observability.events.conflict import (
    CONFLICT_AUTHORITY_DECIDED,
    CONFLICT_CROSS_DEPARTMENT,
    CONFLICT_LCM_LOOKUP,
)

logger = get_logger(__name__)


class AuthorityResolver:
    """Resolve conflicts by seniority and hierarchy position.

    For same-department conflicts, the agent with higher seniority wins.
    For equal seniority, the agent closer to the hierarchy root wins.
    For cross-department conflicts, the lowest common manager is found
    and the agent closer to the LCM wins.

    Args:
        hierarchy: Resolved organizational hierarchy.
    """

    __slots__ = ("_hierarchy",)

    def __init__(self, *, hierarchy: HierarchyResolver) -> None:
        self._hierarchy = hierarchy

    async def resolve(self, conflict: Conflict) -> ConflictResolution:
        """Resolve by authority — highest seniority wins.

        Args:
            conflict: The conflict to resolve.

        Returns:
            Resolution with ``RESOLVED_BY_AUTHORITY`` outcome.

        Raises:
            ConflictHierarchyError: If cross-department agents share
                no common manager.
        """
        if conflict.is_cross_department:
            logger.info(
                CONFLICT_CROSS_DEPARTMENT,
                conflict_id=conflict.id,
            )

        winner, loser = self._pick_winner(conflict)

        logger.info(
            CONFLICT_AUTHORITY_DECIDED,
            conflict_id=conflict.id,
            winner=winner.agent_id,
            loser=loser.agent_id,
        )

        return ConflictResolution(
            conflict_id=conflict.id,
            outcome=ConflictResolutionOutcome.RESOLVED_BY_AUTHORITY,
            winning_agent_id=winner.agent_id,
            winning_position=winner.position,
            decided_by=winner.agent_id,
            reasoning=(
                f"Authority decision: {winner.agent_id} "
                f"({winner.agent_level}) outranks "
                f"{loser.agent_id} ({loser.agent_level})"
            ),
            resolved_at=datetime.now(UTC),
        )

    def build_dissent_record(
        self,
        conflict: Conflict,
        resolution: ConflictResolution,
    ) -> DissentRecord:
        """Build dissent record preserving the losing position.

        Args:
            conflict: The original conflict.
            resolution: The resolution decision.

        Returns:
            Dissent record for the overruled agent.
        """
        loser = _find_loser(conflict, resolution)
        return DissentRecord(
            id=f"dissent-{uuid4().hex[:12]}",
            conflict=conflict,
            resolution=resolution,
            dissenting_agent_id=loser.agent_id,
            dissenting_position=loser.position,
            strategy_used=ConflictResolutionStrategy.AUTHORITY,
            timestamp=datetime.now(UTC),
        )

    def _pick_winner(
        self,
        conflict: Conflict,
    ) -> tuple[ConflictPosition, ConflictPosition]:
        """Determine winner and loser from conflict positions.

        Args:
            conflict: The conflict with agent positions.

        Returns:
            Tuple of ``(winner, loser)``.

        Raises:
            ConflictHierarchyError: If no common manager exists for
                cross-department agents.
        """
        pos_a, pos_b = conflict.positions[0], conflict.positions[1]

        # Compare seniority levels
        cmp = compare_seniority(pos_a.agent_level, pos_b.agent_level)
        if cmp > 0:
            return pos_a, pos_b
        if cmp < 0:
            return pos_b, pos_a

        # Equal seniority — use hierarchy proximity
        return self._resolve_by_hierarchy(conflict, pos_a, pos_b)

    def _resolve_by_hierarchy(
        self,
        conflict: Conflict,
        pos_a: ConflictPosition,
        pos_b: ConflictPosition,
    ) -> tuple[ConflictPosition, ConflictPosition]:
        """Break seniority tie using hierarchy position.

        Args:
            conflict: The conflict being resolved.
            pos_a: First position.
            pos_b: Second position.

        Returns:
            Tuple of ``(winner, loser)``.

        Raises:
            ConflictHierarchyError: If no common manager exists.
        """
        lcm = self._hierarchy.get_lowest_common_manager(
            pos_a.agent_id,
            pos_b.agent_id,
        )
        logger.debug(
            CONFLICT_LCM_LOOKUP,
            conflict_id=conflict.id,
            agent_a=pos_a.agent_id,
            agent_b=pos_b.agent_id,
            lcm=lcm,
        )

        if lcm is None:
            msg = f"No common manager for {pos_a.agent_id!r} and {pos_b.agent_id!r}"
            raise ConflictHierarchyError(
                msg,
                context={
                    "conflict_id": conflict.id,
                    "agent_a": pos_a.agent_id,
                    "agent_b": pos_b.agent_id,
                },
            )

        # Agent closer to LCM (fewer ancestors between) wins
        depth_a = self._hierarchy.get_delegation_depth(lcm, pos_a.agent_id)
        depth_b = self._hierarchy.get_delegation_depth(lcm, pos_b.agent_id)

        # If one agent IS the LCM, their depth is 0
        if depth_a is None:
            depth_a = 0
        if depth_b is None:
            depth_b = 0

        if depth_a <= depth_b:
            return pos_a, pos_b
        return pos_b, pos_a


def _find_loser(
    conflict: Conflict,
    resolution: ConflictResolution,
) -> ConflictPosition:
    """Find the position of the losing agent.

    Args:
        conflict: The original conflict.
        resolution: The resolution decision.

    Returns:
        The losing agent's position.
    """
    for pos in conflict.positions:
        if pos.agent_id != resolution.winning_agent_id:
            return pos
    # Fallback — should never happen with valid data
    return conflict.positions[-1]  # pragma: no cover
