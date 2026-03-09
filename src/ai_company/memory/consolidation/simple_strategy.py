"""Simple consolidation strategy.

Groups old entries by category, keeps the most relevant entry
per group, and creates a summary entry from the rest.
"""

from itertools import groupby
from operator import attrgetter

from ai_company.core.enums import MemoryCategory  # noqa: TC001
from ai_company.core.types import NotBlankStr
from ai_company.memory.consolidation.models import ConsolidationResult
from ai_company.memory.models import MemoryEntry, MemoryMetadata, MemoryStoreRequest
from ai_company.memory.protocol import MemoryBackend  # noqa: TC001
from ai_company.observability import get_logger
from ai_company.observability.events.consolidation import (
    CONSOLIDATION_COMPLETE,
    CONSOLIDATION_START,
)

logger = get_logger(__name__)

_SUMMARY_TRUNCATE_LENGTH = 200

_DEFAULT_GROUP_THRESHOLD = 3


class SimpleConsolidationStrategy:
    """Simple memory consolidation strategy.

    Groups entries by category.  For each group exceeding a threshold,
    keeps the entry with the highest relevance score (or most recent),
    creates a summary entry from the rest, and marks removed entries.

    Args:
        backend: Memory backend for storing summaries.
        group_threshold: Minimum group size to trigger consolidation.
    """

    def __init__(
        self,
        *,
        backend: MemoryBackend,
        group_threshold: int = _DEFAULT_GROUP_THRESHOLD,
    ) -> None:
        self._backend = backend
        self._group_threshold = group_threshold

    async def consolidate(
        self,
        entries: tuple[MemoryEntry, ...],
        *,
        agent_id: NotBlankStr,
    ) -> ConsolidationResult:
        """Consolidate entries by grouping and summarizing per category.

        Args:
            entries: Memory entries to consolidate.
            agent_id: Owning agent identifier.

        Returns:
            Result describing what was consolidated.
        """
        if not entries:
            return ConsolidationResult(consolidated_count=0)

        logger.info(
            CONSOLIDATION_START,
            agent_id=agent_id,
            entry_count=len(entries),
        )

        removed_ids: list[NotBlankStr] = []
        summary_id: NotBlankStr | None = None

        sorted_entries = sorted(entries, key=attrgetter("category"))
        groups = groupby(sorted_entries, key=attrgetter("category"))

        for category, group_iter in groups:
            group = list(group_iter)
            if len(group) < self._group_threshold:
                continue

            _kept, to_remove = self._select_entries(group)
            summary_content = self._build_summary(category, to_remove)

            store_request = MemoryStoreRequest(
                category=category,
                content=summary_content,
                metadata=MemoryMetadata(
                    source="consolidation",
                    tags=("consolidated",),
                ),
            )
            new_id = await self._backend.store(agent_id, store_request)
            if summary_id is None:
                summary_id = new_id

            for entry in to_remove:
                await self._backend.delete(agent_id, entry.id)
                removed_ids.append(NotBlankStr(entry.id))

        result = ConsolidationResult(
            consolidated_count=len(removed_ids),
            removed_ids=tuple(removed_ids),
            summary_id=summary_id,
        )

        logger.info(
            CONSOLIDATION_COMPLETE,
            agent_id=agent_id,
            consolidated_count=result.consolidated_count,
            summary_id=result.summary_id,
        )

        return result

    def _select_entries(
        self,
        group: list[MemoryEntry],
    ) -> tuple[MemoryEntry, list[MemoryEntry]]:
        """Select the best entry to keep and the rest to remove.

        Args:
            group: Entries in the same category.

        Returns:
            Tuple of (kept entry, entries to remove).
        """
        best = max(
            group,
            key=lambda e: (
                e.relevance_score if e.relevance_score is not None else 0.0,
                e.created_at,
            ),
        )
        to_remove = [e for e in group if e.id != best.id]
        return best, to_remove

    def _build_summary(
        self,
        category: MemoryCategory,
        entries: list[MemoryEntry],
    ) -> str:
        """Build a summary text from removed entries.

        Args:
            category: The memory category.
            entries: Entries being consolidated.

        Returns:
            Summary text combining key content.
        """
        lines = [f"Consolidated {category.value} memories:"]
        for entry in entries:
            truncated = (
                entry.content[:_SUMMARY_TRUNCATE_LENGTH] + "..."
                if len(entry.content) > _SUMMARY_TRUNCATE_LENGTH
                else entry.content
            )
            lines.append(f"- {truncated}")
        return "\n".join(lines)
