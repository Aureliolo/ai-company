"""LLM-based memory consolidation strategy.

Feeds related memories (grouped by category) to an LLM for semantic
deduplication and synthesis.  Falls back to simple concatenation when
the LLM call fails with a retryable error.
"""

from itertools import groupby
from operator import attrgetter

from synthorg.core.enums import MemoryCategory  # noqa: TC001
from synthorg.core.types import NotBlankStr  # noqa: TC001
from synthorg.memory.consolidation.models import ConsolidationResult
from synthorg.memory.models import MemoryEntry, MemoryMetadata, MemoryStoreRequest
from synthorg.memory.protocol import MemoryBackend  # noqa: TC001
from synthorg.observability import get_logger
from synthorg.observability.events.consolidation import (
    LLM_STRATEGY_FALLBACK,
    LLM_STRATEGY_SYNTHESIZED,
    STRATEGY_COMPLETE,
    STRATEGY_START,
)
from synthorg.providers.enums import MessageRole
from synthorg.providers.errors import ProviderError
from synthorg.providers.models import ChatMessage, CompletionConfig
from synthorg.providers.protocol import CompletionProvider  # noqa: TC001

logger = get_logger(__name__)

_DEFAULT_GROUP_THRESHOLD = 3
_MIN_GROUP_THRESHOLD = 2
_FALLBACK_TRUNCATE_LENGTH = 200

_SYSTEM_PROMPT = (
    "You are a memory consolidation assistant. You will receive multiple "
    "memory entries from the same category. Your task is to:\n"
    "1. Identify duplicate or overlapping information across entries\n"
    "2. Merge semantically related facts into concise statements\n"
    "3. Preserve ALL unique information: specific details, IDs, dates, "
    "names, decisions, and outcomes\n"
    "4. Return a single synthesized summary that is shorter than the "
    "combined input but retains all distinct facts\n\n"
    "Respond with ONLY the synthesized summary, nothing else."
)


class LLMConsolidationStrategy:
    """LLM-based memory consolidation strategy.

    Groups entries by category.  For each group exceeding the threshold,
    keeps the entry with the highest relevance score (with most recent
    as tiebreaker), feeds the rest to an LLM for semantic synthesis,
    stores the synthesized summary, and deletes the consolidated entries.

    Falls back to simple concatenation if the LLM call fails with a
    retryable error or returns empty content.

    Args:
        backend: Memory backend for storing summaries.
        provider: Completion provider for LLM synthesis calls.
        model: Model identifier for the synthesis LLM.
        group_threshold: Minimum group size to trigger consolidation
            (must be >= 2).
        temperature: Sampling temperature for synthesis.
        max_summary_tokens: Maximum tokens for the synthesis response.

    Raises:
        ValueError: If ``group_threshold`` is less than 2.
    """

    def __init__(  # noqa: PLR0913
        self,
        *,
        backend: MemoryBackend,
        provider: CompletionProvider,
        model: NotBlankStr,
        group_threshold: int = _DEFAULT_GROUP_THRESHOLD,
        temperature: float = 0.3,
        max_summary_tokens: int = 500,
    ) -> None:
        if group_threshold < _MIN_GROUP_THRESHOLD:
            msg = (
                f"group_threshold must be >= {_MIN_GROUP_THRESHOLD}, "
                f"got {group_threshold}"
            )
            raise ValueError(msg)
        self._backend = backend
        self._provider = provider
        self._model = model
        self._group_threshold = group_threshold
        self._completion_config = CompletionConfig(
            temperature=temperature,
            max_tokens=max_summary_tokens,
        )

    async def consolidate(
        self,
        entries: tuple[MemoryEntry, ...],
        *,
        agent_id: NotBlankStr,
    ) -> ConsolidationResult:
        """Consolidate entries using LLM-based semantic synthesis.

        Groups entries by category, selects the best entry per group
        to keep, synthesizes the rest via LLM, stores the summary,
        and deletes consolidated entries.

        Args:
            entries: Memory entries to consolidate.
            agent_id: Owning agent identifier.

        Returns:
            Result describing what was consolidated.
        """
        if not entries:
            return ConsolidationResult()

        logger.info(
            STRATEGY_START,
            agent_id=agent_id,
            entry_count=len(entries),
            strategy="llm",
        )

        removed_ids: list[NotBlankStr] = []
        summary_id: NotBlankStr | None = None

        sorted_entries = sorted(entries, key=attrgetter("category"))
        groups = groupby(sorted_entries, key=attrgetter("category"))

        for category, group_iter in groups:
            group = list(group_iter)
            if len(group) < self._group_threshold:
                continue

            new_id, group_removed = await self._process_group(
                category,
                group,
                agent_id,
            )
            if summary_id is None:
                summary_id = new_id
            removed_ids.extend(group_removed)

        result = ConsolidationResult(
            removed_ids=tuple(removed_ids),
            summary_id=summary_id,
        )

        logger.info(
            STRATEGY_COMPLETE,
            agent_id=agent_id,
            consolidated_count=result.consolidated_count,
            summary_id=result.summary_id,
            strategy="llm",
        )

        return result

    async def _process_group(
        self,
        category: MemoryCategory,
        group: list[MemoryEntry],
        agent_id: NotBlankStr,
    ) -> tuple[NotBlankStr, list[NotBlankStr]]:
        """Process a single category group for consolidation.

        Args:
            category: The memory category.
            group: Entries in this category.
            agent_id: Owning agent identifier.

        Returns:
            Tuple of (summary_id, removed_ids).
        """
        _, to_remove = self._select_entries(group)
        summary_content = await self._synthesize(to_remove)

        store_request = MemoryStoreRequest(
            category=category,
            content=summary_content,
            metadata=MemoryMetadata(
                source="consolidation",
                tags=("consolidated", "llm-synthesized"),
            ),
        )
        new_id = await self._backend.store(agent_id, store_request)

        removed_ids: list[NotBlankStr] = []
        for entry in to_remove:
            await self._backend.delete(agent_id, entry.id)
            removed_ids.append(entry.id)

        return new_id, removed_ids

    async def _synthesize(
        self,
        entries: list[MemoryEntry],
    ) -> str:
        """Synthesize multiple entries into a single summary via LLM.

        Falls back to simple concatenation on retryable errors or
        empty responses.  Non-retryable provider errors propagate.

        Args:
            entries: Entries to synthesize.

        Returns:
            Synthesized summary text.
        """
        user_content = "\n---\n".join(
            f"[{e.category.value}] {e.content}" for e in entries
        )

        try:
            messages = [
                ChatMessage(role=MessageRole.SYSTEM, content=_SYSTEM_PROMPT),
                ChatMessage(role=MessageRole.USER, content=user_content),
            ]
            response = await self._provider.complete(
                messages,
                self._model,
                config=self._completion_config,
            )
            if response.content and response.content.strip():
                logger.debug(
                    LLM_STRATEGY_SYNTHESIZED,
                    entry_count=len(entries),
                    input_length=len(user_content),
                    output_length=len(response.content),
                    model=self._model,
                )
                return response.content.strip()
        except MemoryError, RecursionError:
            raise
        except ProviderError as exc:
            if not exc.is_retryable:
                raise
            logger.warning(
                LLM_STRATEGY_FALLBACK,
                entry_count=len(entries),
                error=str(exc),
                error_type=type(exc).__name__,
                reason="retryable_provider_error",
            )
            return self._fallback_summary(entries)
        except Exception as exc:
            logger.warning(
                LLM_STRATEGY_FALLBACK,
                entry_count=len(entries),
                error=str(exc),
                error_type=type(exc).__name__,
                reason="unexpected_error",
            )
            return self._fallback_summary(entries)

        # Empty/whitespace-only LLM response
        logger.debug(
            LLM_STRATEGY_FALLBACK,
            entry_count=len(entries),
            reason="empty_response",
        )
        return self._fallback_summary(entries)

    def _fallback_summary(self, entries: list[MemoryEntry]) -> str:
        """Build a simple concatenation summary as fallback.

        Args:
            entries: Entries being consolidated.

        Returns:
            Concatenated summary text.
        """
        lines = [f"Consolidated {entries[0].category.value} memories:"]
        for entry in entries:
            truncated = (
                entry.content[:_FALLBACK_TRUNCATE_LENGTH] + "..."
                if len(entry.content) > _FALLBACK_TRUNCATE_LENGTH
                else entry.content
            )
            lines.append(f"- {truncated}")
        return "\n".join(lines)

    def _select_entries(
        self,
        group: list[MemoryEntry],
    ) -> tuple[MemoryEntry, list[MemoryEntry]]:
        """Select the best entry to keep and the rest to remove.

        Entries with ``None`` relevance scores are treated as ``0.0``
        for comparison.  When scores are equal, the most recently
        created entry wins.

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
