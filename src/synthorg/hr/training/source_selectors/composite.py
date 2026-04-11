"""Composite source selector.

Combines multiple selectors, merges their results, and
deduplicates agent IDs while preserving order.
"""

from typing import TYPE_CHECKING

from synthorg.observability import get_logger
from synthorg.observability.events.training import (
    HR_TRAINING_EXTRACTION_STARTED,
)

if TYPE_CHECKING:
    from synthorg.core.enums import SeniorityLevel
    from synthorg.core.types import NotBlankStr
    from synthorg.hr.training.protocol import SourceSelector

logger = get_logger(__name__)


class CompositeSelector:
    """Combine multiple selectors with weighted voting.

    Runs all child selectors, merges results, and deduplicates.
    Weights are stored for future scoring but currently all
    selector outputs are merged equally.

    Args:
        selectors: Child selectors.
        weights: Per-selector weights (for future use).
    """

    def __init__(
        self,
        *,
        selectors: tuple[SourceSelector, ...],
        weights: tuple[float, ...],
    ) -> None:
        self._selectors = selectors
        self._weights = weights

    @property
    def name(self) -> str:
        """Selector strategy name."""
        return "composite"

    async def select(
        self,
        *,
        new_agent_role: NotBlankStr,
        new_agent_level: SeniorityLevel,
    ) -> tuple[NotBlankStr, ...]:
        """Run all child selectors and merge results.

        Args:
            new_agent_role: Role of the new hire.
            new_agent_level: Seniority level.

        Returns:
            Deduplicated merged agent IDs.
        """
        if not self._selectors:
            return ()

        seen: set[str] = set()
        result: list[str] = []

        for selector in self._selectors:
            ids = await selector.select(
                new_agent_role=new_agent_role,
                new_agent_level=new_agent_level,
            )
            for agent_id in ids:
                str_id = str(agent_id)
                if str_id not in seen:
                    seen.add(str_id)
                    result.append(str_id)

        logger.debug(
            HR_TRAINING_EXTRACTION_STARTED,
            selector="composite",
            child_count=len(self._selectors),
            total_selected=len(result),
        )
        return tuple(result)
