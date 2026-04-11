"""Department diversity sampling source selector.

Selects a mix of top performers and complementary-role agents
from the new hire's department.
"""

from typing import TYPE_CHECKING

from synthorg.observability import get_logger
from synthorg.observability.events.training import (
    HR_TRAINING_EXTRACTION_STARTED,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from synthorg.core.agent import AgentIdentity
    from synthorg.core.enums import SeniorityLevel
    from synthorg.core.types import NotBlankStr
    from synthorg.hr.performance.tracker import PerformanceTracker
    from synthorg.hr.registry import AgentRegistryService

logger = get_logger(__name__)

_DEFAULT_TOP_PERFORMER_COUNT = 2
_DEFAULT_COMPLEMENTARY_COUNT = 2


class DepartmentDiversitySampling:
    """Select a diverse sample from the new hire's department.

    Splits department agents into same-role (top performers) and
    different-role (complementary), then selects from each group.

    Args:
        registry: Agent registry service.
        tracker: Performance tracker.
        top_performer_count: Number of same-role top performers.
        complementary_count: Number of different-role agents.
    """

    def __init__(
        self,
        *,
        registry: AgentRegistryService,
        tracker: PerformanceTracker,
        top_performer_count: int = _DEFAULT_TOP_PERFORMER_COUNT,
        complementary_count: int = _DEFAULT_COMPLEMENTARY_COUNT,
    ) -> None:
        self._registry = registry
        self._tracker = tracker
        self._top_performer_count = top_performer_count
        self._complementary_count = complementary_count

    @property
    def name(self) -> str:
        """Selector strategy name."""
        return "department_diversity"

    async def select(
        self,
        *,
        new_agent_role: NotBlankStr,
        new_agent_level: SeniorityLevel,  # noqa: ARG002
    ) -> tuple[NotBlankStr, ...]:
        """Select diverse agents from the department.

        Args:
            new_agent_role: Role of the new hire.
            new_agent_level: Seniority level (unused, reserved).

        Returns:
            Agent IDs mixing top performers and complementary roles.
        """
        # Infer department from active agents with matching role.
        active = await self._registry.list_active()
        role_lower = str(new_agent_role).lower()
        department = None
        for agent in active:
            if str(agent.role).lower() == role_lower:
                department = str(agent.department)
                break

        if department is None:
            logger.debug(
                HR_TRAINING_EXTRACTION_STARTED,
                selector="department_diversity",
                role=str(new_agent_role),
                candidates=0,
            )
            return ()

        dept_agents = await self._registry.list_by_department(
            department,
        )
        if not dept_agents:
            return ()

        same_role = [a for a in dept_agents if str(a.role).lower() == role_lower]
        diff_role = [a for a in dept_agents if str(a.role).lower() != role_lower]

        top_performers = await self._rank_by_quality(
            same_role,
            self._top_performer_count,
        )
        complementary = await self._rank_by_quality(
            diff_role,
            self._complementary_count,
        )

        # Merge and deduplicate preserving order.
        seen: set[str] = set()
        result: list[str] = []
        for agent_id in (*top_performers, *complementary):
            if agent_id not in seen:
                seen.add(agent_id)
                result.append(agent_id)

        logger.debug(
            HR_TRAINING_EXTRACTION_STARTED,
            selector="department_diversity",
            department=department,
            top_performers=len(top_performers),
            complementary=len(complementary),
        )
        return tuple(result)

    async def _rank_by_quality(
        self,
        agents: Sequence[AgentIdentity],
        limit: int,
    ) -> tuple[str, ...]:
        """Rank agents by quality score and return top N IDs."""
        scored: list[tuple[float, str]] = []
        for agent in agents:
            snapshot = await self._tracker.get_snapshot(
                str(agent.id),
            )
            score = snapshot.overall_quality_score or 0.0
            scored.append((score, str(agent.id)))

        scored.sort(key=lambda x: x[0], reverse=True)
        return tuple(agent_id for _, agent_id in scored[:limit])
