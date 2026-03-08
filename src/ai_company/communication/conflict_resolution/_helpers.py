"""Shared helpers for conflict resolution strategies."""

from ai_company.communication.conflict_resolution.models import (  # noqa: TC001
    Conflict,
    ConflictPosition,
    ConflictResolution,
)
from ai_company.communication.errors import (
    ConflictStrategyError,
)
from ai_company.core.enums import compare_seniority


def find_loser(
    conflict: Conflict,
    resolution: ConflictResolution,
) -> ConflictPosition:
    """Find the position of the first non-winning agent.

    Args:
        conflict: The original conflict.
        resolution: The resolution decision.

    Returns:
        The first losing agent's position.

    Raises:
        ConflictStrategyError: If no losing position is found
            (data integrity violation).
    """
    for pos in conflict.positions:
        if pos.agent_id != resolution.winning_agent_id:
            return pos
    msg = f"No losing position found for winner {resolution.winning_agent_id!r}"
    raise ConflictStrategyError(
        msg,
        context={"conflict_id": conflict.id},
    )


def find_position(
    conflict: Conflict,
    agent_id: str,
) -> ConflictPosition | None:
    """Find a position by agent ID, or None if not found.

    Args:
        conflict: The conflict.
        agent_id: Agent to find.

    Returns:
        The matching position, or None.
    """
    for pos in conflict.positions:
        if pos.agent_id == agent_id:
            return pos
    return None


def find_position_or_raise(
    conflict: Conflict,
    agent_id: str,
) -> ConflictPosition:
    """Find a position by agent ID, raising if not found.

    Args:
        conflict: The conflict.
        agent_id: Agent to find.

    Returns:
        The matching position.

    Raises:
        ConflictStrategyError: If agent is not found in positions.
    """
    pos = find_position(conflict, agent_id)
    if pos is not None:
        return pos
    msg = f"Agent {agent_id!r} not found in conflict positions"
    raise ConflictStrategyError(
        msg,
        context={
            "conflict_id": conflict.id,
            "agent_id": agent_id,
        },
    )


def pick_highest_seniority(
    conflict: Conflict,
) -> ConflictPosition:
    """Pick the position with the highest seniority level.

    Args:
        conflict: The conflict with agent positions.

    Returns:
        The position with the highest seniority.
    """
    best = conflict.positions[0]
    for pos in conflict.positions[1:]:
        if compare_seniority(pos.agent_level, best.agent_level) > 0:
            best = pos
    return best
