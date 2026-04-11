"""User-curated source selector.

Passes through an explicit list of agent IDs provided by the
user, validating that each agent exists in the registry.
"""

from typing import TYPE_CHECKING

from synthorg.observability import get_logger
from synthorg.observability.events.training import (
    HR_TRAINING_EXTRACTION_STARTED,
)

if TYPE_CHECKING:
    from synthorg.core.enums import SeniorityLevel
    from synthorg.core.types import NotBlankStr
    from synthorg.hr.registry import AgentRegistryService

logger = get_logger(__name__)


class UserCuratedList:
    """Pass-through selector for user-provided agent IDs.

    Validates that all provided agent IDs exist in the registry,
    filtering out any that are not found.

    Args:
        registry: Agent registry service.
        agent_ids: Explicit list of agent IDs.
    """

    def __init__(
        self,
        *,
        registry: AgentRegistryService,
        agent_ids: tuple[str, ...],
    ) -> None:
        self._registry = registry
        self._agent_ids = agent_ids

    @property
    def name(self) -> str:
        """Selector strategy name."""
        return "user_curated"

    async def select(
        self,
        *,
        new_agent_role: NotBlankStr,  # noqa: ARG002
        new_agent_level: SeniorityLevel,  # noqa: ARG002
    ) -> tuple[NotBlankStr, ...]:
        """Return the user-provided agent IDs, filtering invalid ones.

        Args:
            new_agent_role: Role of the new hire (unused).
            new_agent_level: Seniority level (unused).

        Returns:
            Validated agent IDs.
        """
        if not self._agent_ids:
            return ()

        valid: list[str] = []
        for agent_id in self._agent_ids:
            identity = await self._registry.get(agent_id)
            if identity is not None:
                valid.append(agent_id)
            else:
                logger.warning(
                    HR_TRAINING_EXTRACTION_STARTED,
                    selector="user_curated",
                    agent_id=agent_id,
                    skipped="not_found",
                )

        return tuple(valid)
