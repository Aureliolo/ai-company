"""Role-based top performers source selector.

Selects the top N agents in the new hire's role, ranked by recent
quality score from the performance tracker.
"""

from typing import TYPE_CHECKING

from synthorg.observability import get_logger
from synthorg.observability.events.training import (
    HR_TRAINING_EXTRACTION_STARTED,
)

if TYPE_CHECKING:
    from synthorg.core.enums import SeniorityLevel
    from synthorg.core.types import NotBlankStr
    from synthorg.hr.performance.tracker import PerformanceTracker
    from synthorg.hr.registry import AgentRegistryService

logger = get_logger(__name__)

_DEFAULT_TOP_N = 3


class RoleTopPerformers:
    """Select top N performers in the new hire's role.

    Queries the registry for active agents matching the role,
    fetches performance snapshots, and returns the top N by
    overall quality score.

    Args:
        registry: Agent registry service.
        tracker: Performance tracker.
        top_n: Number of top performers to select.
    """

    def __init__(
        self,
        *,
        registry: AgentRegistryService,
        tracker: PerformanceTracker,
        top_n: int = _DEFAULT_TOP_N,
    ) -> None:
        self._registry = registry
        self._tracker = tracker
        self._top_n = top_n

    @property
    def name(self) -> str:
        """Selector strategy name."""
        return "role_top_performers"

    async def select(
        self,
        *,
        new_agent_role: NotBlankStr,
        new_agent_level: SeniorityLevel,  # noqa: ARG002
    ) -> tuple[NotBlankStr, ...]:
        """Select top N agents in the same role by quality score.

        Args:
            new_agent_role: Role of the new hire.
            new_agent_level: Seniority level (unused, reserved).

        Returns:
            Agent IDs ordered by quality score descending.
        """
        active = await self._registry.list_active()
        role_lower = str(new_agent_role).lower()
        candidates = [a for a in active if str(a.role).lower() == role_lower]

        if not candidates:
            logger.debug(
                HR_TRAINING_EXTRACTION_STARTED,
                selector="role_top_performers",
                role=str(new_agent_role),
                candidates=0,
            )
            return ()

        scored: list[tuple[float, str]] = []
        for agent in candidates:
            snapshot = await self._tracker.get_snapshot(
                str(agent.id),
            )
            score = snapshot.overall_quality_score or 0.0
            scored.append((score, str(agent.id)))

        scored.sort(key=lambda x: x[0], reverse=True)
        selected = tuple(agent_id for _, agent_id in scored[: self._top_n])

        logger.debug(
            HR_TRAINING_EXTRACTION_STARTED,
            selector="role_top_performers",
            role=str(new_agent_role),
            candidates=len(candidates),
            selected=len(selected),
        )
        return selected
