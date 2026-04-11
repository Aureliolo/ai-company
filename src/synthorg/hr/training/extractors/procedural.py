"""Procedural memory content extractor.

Queries the memory backend for procedural-category entries from
source agents and converts them to training items.
"""

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from synthorg.core.enums import MemoryCategory
from synthorg.hr.training.models import ContentType, TrainingItem
from synthorg.memory.models import MemoryQuery
from synthorg.observability import get_logger
from synthorg.observability.events.training import (
    HR_TRAINING_ITEMS_EXTRACTED,
)

if TYPE_CHECKING:
    from synthorg.core.enums import SeniorityLevel
    from synthorg.core.types import NotBlankStr
    from synthorg.memory.protocol import MemoryBackend

logger = get_logger(__name__)

_MAX_ENTRIES_PER_AGENT = 100


class ProceduralMemoryExtractor:
    """Extract procedural memory entries from senior agents.

    Queries the memory backend for ``PROCEDURAL`` category entries
    from each source agent and converts them to ``TrainingItem``
    instances.

    Args:
        backend: Memory backend for retrieval.
    """

    def __init__(self, *, backend: MemoryBackend) -> None:
        self._backend = backend

    @property
    def content_type(self) -> ContentType:
        """The content type this extractor produces."""
        return ContentType.PROCEDURAL

    async def extract(
        self,
        *,
        source_agent_ids: tuple[NotBlankStr, ...],
        new_agent_role: NotBlankStr,  # noqa: ARG002
        new_agent_level: SeniorityLevel,  # noqa: ARG002
    ) -> tuple[TrainingItem, ...]:
        """Extract procedural memories from source agents.

        Args:
            source_agent_ids: Senior agents to extract from.
            new_agent_role: Role of the new hire (unused).
            new_agent_level: Seniority level (unused).

        Returns:
            Unranked procedural training items.
        """
        if not source_agent_ids:
            return ()

        items: list[TrainingItem] = []
        query = MemoryQuery(
            categories=frozenset({MemoryCategory.PROCEDURAL}),
            limit=_MAX_ENTRIES_PER_AGENT,
        )

        for agent_id in source_agent_ids:
            entries = await self._backend.retrieve(agent_id, query)
            items.extend(
                TrainingItem(
                    source_agent_id=str(agent_id),
                    content_type=ContentType.PROCEDURAL,
                    content=str(entry.content),
                    source_memory_id=str(entry.id),
                    metadata_tags=entry.metadata.tags,
                    created_at=datetime.now(UTC),
                )
                for entry in entries
            )

        logger.debug(
            HR_TRAINING_ITEMS_EXTRACTED,
            content_type="procedural",
            agent_count=len(source_agent_ids),
            item_count=len(items),
        )
        return tuple(items)
