"""Denial tracker for deny-and-continue with retry tracking.

Tracks consecutive and total denial counts per agent.  When an agent
hits the maximum consecutive denials or maximum total denials, the
tracker signals escalation to human review.

Counts are in-memory only -- they reset on process restart.  This is
intentional: persistent denial counts would need careful TTL and
garbage-collection logic, and the current use case (short-lived agent
execution loops) does not require persistence.
"""

from enum import StrEnum

from synthorg.observability import get_logger
from synthorg.observability.events.security import (
    SECURITY_DENIAL_ESCALATED,
    SECURITY_DENIAL_RECORDED,
    SECURITY_DENIAL_RESET,
)

logger = get_logger(__name__)


class DenialAction(StrEnum):
    """Action to take after recording a denial.

    Members:
        RETRY: Agent may retry with a safer approach.
        ESCALATE: Maximum denials reached -- escalate to human.
    """

    RETRY = "retry"
    ESCALATE = "escalate"


class _AgentDenialCounts:
    """Mutable denial counts for a single agent.

    Not exposed publicly -- internal bookkeeping only.
    """

    __slots__ = ("consecutive", "total")

    def __init__(self) -> None:
        self.consecutive: int = 0
        self.total: int = 0


class DenialTracker:
    """Track consecutive and total denials per agent.

    Thread-safe for async use: each method operates on a single
    dict lookup + mutation per call, and asyncio is single-threaded
    within an event loop.

    Args:
        max_consecutive: Maximum consecutive denials before escalation.
        max_total: Maximum total denials before escalation.
    """

    def __init__(
        self,
        *,
        max_consecutive: int,
        max_total: int,
    ) -> None:
        if max_consecutive < 1:
            msg = f"max_consecutive must be >= 1, got {max_consecutive}"
            raise ValueError(msg)
        if max_total < 1:
            msg = f"max_total must be >= 1, got {max_total}"
            raise ValueError(msg)
        self._max_consecutive = max_consecutive
        self._max_total = max_total
        self._counts: dict[str, _AgentDenialCounts] = {}

    def record_denial(self, agent_id: str) -> DenialAction:
        """Record a denial for an agent and return the action.

        Args:
            agent_id: The agent identifier.

        Returns:
            ``DenialAction.RETRY`` if the agent may retry, or
            ``DenialAction.ESCALATE`` if limits are reached.
        """
        counts = self._counts.get(agent_id)
        if counts is None:
            counts = _AgentDenialCounts()
            self._counts[agent_id] = counts

        counts.consecutive += 1
        counts.total += 1

        if (
            counts.consecutive >= self._max_consecutive
            or counts.total >= self._max_total
        ):
            logger.warning(
                SECURITY_DENIAL_ESCALATED,
                agent_id=agent_id,
                consecutive=counts.consecutive,
                total=counts.total,
                max_consecutive=self._max_consecutive,
                max_total=self._max_total,
            )
            return DenialAction.ESCALATE

        logger.info(
            SECURITY_DENIAL_RECORDED,
            agent_id=agent_id,
            consecutive=counts.consecutive,
            total=counts.total,
        )
        return DenialAction.RETRY

    def reset_consecutive(self, agent_id: str) -> None:
        """Reset the consecutive denial count for an agent.

        Called when the agent succeeds (action classified as SAFE
        or SUSPICIOUS).  Total count is preserved.

        Args:
            agent_id: The agent identifier.
        """
        counts = self._counts.get(agent_id)
        if counts is not None and counts.consecutive > 0:
            logger.debug(
                SECURITY_DENIAL_RESET,
                agent_id=agent_id,
                previous_consecutive=counts.consecutive,
            )
            counts.consecutive = 0

    def get_counts(self, agent_id: str) -> tuple[int, int]:
        """Return (consecutive, total) denial counts for an agent.

        Args:
            agent_id: The agent identifier.

        Returns:
            A tuple of ``(consecutive_denials, total_denials)``.
            Returns ``(0, 0)`` if the agent has no recorded denials.
        """
        counts = self._counts.get(agent_id)
        if counts is None:
            return (0, 0)
        return (counts.consecutive, counts.total)
