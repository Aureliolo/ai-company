"""LLM-based memory consolidation strategy.

Feeds related memories (grouped by category) to an LLM for semantic
deduplication and synthesis.  When distillation entries (tagged
``"distillation"`` by ``capture_distillation``) exist for the agent,
their trajectory summaries and outcomes are included in the synthesis
system prompt as context.

Falls back to simple concatenation when the LLM call fails with a
retryable error (after retries are exhausted) or returns empty content.
"""

import asyncio
from itertools import groupby
from operator import attrgetter

from synthorg.core.enums import MemoryCategory  # noqa: TC001
from synthorg.core.types import NotBlankStr  # noqa: TC001
from synthorg.memory.consolidation.models import ConsolidationResult
from synthorg.memory.models import (
    MemoryEntry,
    MemoryMetadata,
    MemoryQuery,
    MemoryStoreRequest,
)
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
from synthorg.providers.resilience.errors import RetryExhaustedError

logger = get_logger(__name__)

_DEFAULT_GROUP_THRESHOLD = 3
_MIN_GROUP_THRESHOLD = 2
_FALLBACK_TRUNCATE_LENGTH = 200
_MAX_ENTRY_INPUT_CHARS = 2000
_MAX_TRAJECTORY_CONTEXT_ENTRIES = 5
_MAX_TRAJECTORY_CHARS_PER_ENTRY = 500

#: Tag read from the backend to locate distillation entries produced
#: by ``synthorg.memory.consolidation.distillation.capture_distillation``.
#: Kept as a literal here to avoid a cross-module import that would
#: pull the engine execution protocol into the consolidation strategy
#: module unnecessarily.
_DISTILLATION_TAG: NotBlankStr = "distillation"

#: Tag applied to LLM-produced summaries.  Used to distinguish them
#: from the concatenation fallback (tagged with ``_CONCAT_FALLBACK_TAG``).
_LLM_SYNTHESIZED_TAG: NotBlankStr = "llm-synthesized"

#: Tag applied to concatenation-fallback summaries.
_CONCAT_FALLBACK_TAG: NotBlankStr = "concat-fallback"

_BASE_SYSTEM_PROMPT = (
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
    as tiebreaker).  The kept entry is NOT included in the LLM
    synthesis input -- it remains in the backend unchanged, while the
    remaining entries are fed to the LLM, the synthesized summary is
    stored, and the originals are deleted.

    Category groups are processed in parallel via ``asyncio.TaskGroup``.

    When an agent has distillation entries (memory entries tagged
    ``"distillation"`` by ``capture_distillation``) present in the
    backend, a best-effort lookup fetches the most recent ones and
    includes their trajectory summaries and outcomes in the synthesis
    system prompt as trajectory context.  Lookup failures degrade
    silently (no trajectory context -- plain synthesis).

    Falls back to simple concatenation when ``provider.complete``
    raises ``RetryExhaustedError`` (all retries consumed) or returns
    an empty/whitespace response.  Non-retryable ``ProviderError``
    subclasses propagate to the caller.  Unexpected non-provider
    exceptions also fall back to concatenation (logged at WARNING
    with full traceback).

    Args:
        backend: Memory backend for storing summaries and reading
            distillation entries.
        provider: Completion provider for LLM synthesis calls.
        model: Model identifier for the synthesis LLM.
        group_threshold: Minimum group size to trigger consolidation
            (must be >= 2).
        temperature: Sampling temperature for synthesis.
        max_summary_tokens: Maximum tokens for the synthesis response.
        include_distillation_context: When True (default), fetches
            recent distillation entries as trajectory context for the
            synthesis prompt.  Set False to skip the lookup entirely.

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
        include_distillation_context: bool = True,
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
        self._include_distillation_context = include_distillation_context
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

        Groups entries by category, fetches distillation trajectory
        context (when enabled), and processes groups in parallel.
        For each group exceeding ``group_threshold``, selects the
        best entry to keep, synthesizes the rest via LLM with optional
        trajectory context, stores the summary, and deletes the
        consolidated entries.

        ``ConsolidationResult.summary_id`` reflects the LAST summary
        produced (most recent category processed).  Per-group summary
        IDs are emitted via the ``LLM_STRATEGY_SYNTHESIZED`` log event
        for full observability.

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

        trajectory_context = await self._fetch_trajectory_context(agent_id)

        groups_to_process: list[tuple[MemoryCategory, list[MemoryEntry]]] = []
        sorted_entries = sorted(entries, key=attrgetter("category"))
        for category, group_iter in groupby(sorted_entries, key=attrgetter("category")):
            group = list(group_iter)
            if len(group) >= self._group_threshold:
                groups_to_process.append((category, group))

        group_results: list[tuple[NotBlankStr, list[NotBlankStr]]] = []
        if groups_to_process:
            try:
                async with asyncio.TaskGroup() as tg:
                    tasks = [
                        tg.create_task(
                            self._process_group(
                                category,
                                group,
                                agent_id,
                                trajectory_context,
                            )
                        )
                        for category, group in groups_to_process
                    ]
            # TaskGroup wraps task exceptions in ExceptionGroup.
            # Log the full group before unwrapping so operators can
            # diagnose multi-task failures, then re-raise the first
            # exception so callers see the original error type they
            # would have seen from sequential processing.
            except* MemoryError as eg:
                logger.error(
                    LLM_STRATEGY_FALLBACK,
                    agent_id=agent_id,
                    reason="task_group_memory_error",
                    exception_count=len(eg.exceptions),
                    exc_info=True,
                )
                raise eg.exceptions[0] from eg
            except* RecursionError as eg:
                logger.error(
                    LLM_STRATEGY_FALLBACK,
                    agent_id=agent_id,
                    reason="task_group_recursion_error",
                    exception_count=len(eg.exceptions),
                    exc_info=True,
                )
                raise eg.exceptions[0] from eg
            except* ProviderError as eg:
                logger.error(
                    LLM_STRATEGY_FALLBACK,
                    agent_id=agent_id,
                    reason="task_group_provider_error",
                    exception_count=len(eg.exceptions),
                    exc_info=True,
                )
                raise eg.exceptions[0] from eg
            except* Exception as eg:
                logger.error(
                    LLM_STRATEGY_FALLBACK,
                    agent_id=agent_id,
                    reason="task_group_unexpected_error",
                    exception_count=len(eg.exceptions),
                    exc_info=True,
                )
                raise eg.exceptions[0] from eg
            group_results = [task.result() for task in tasks]

        removed_ids: list[NotBlankStr] = []
        summary_id: NotBlankStr | None = None
        for new_id, group_removed in group_results:
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

    async def _fetch_trajectory_context(
        self,
        agent_id: NotBlankStr,
    ) -> tuple[MemoryEntry, ...]:
        """Fetch recent distillation entries as trajectory context.

        Best-effort: failures degrade to empty context (no trajectory
        information included in the synthesis prompt).  Returns at most
        ``_MAX_TRAJECTORY_CONTEXT_ENTRIES`` entries.
        """
        if not self._include_distillation_context:
            return ()
        try:
            query = MemoryQuery(
                tags=(_DISTILLATION_TAG,),
                limit=_MAX_TRAJECTORY_CONTEXT_ENTRIES,
            )
            return await self._backend.retrieve(agent_id, query)
        except MemoryError, RecursionError:
            logger.error(
                LLM_STRATEGY_FALLBACK,
                agent_id=agent_id,
                reason="system_error_in_trajectory_fetch",
                error_type="system",
                exc_info=True,
            )
            raise
        except Exception as exc:
            logger.debug(
                LLM_STRATEGY_FALLBACK,
                agent_id=agent_id,
                reason="distillation_lookup_failed",
                error=str(exc),
                error_type=type(exc).__name__,
            )
            return ()

    async def _process_group(
        self,
        category: MemoryCategory,
        group: list[MemoryEntry],
        agent_id: NotBlankStr,
        trajectory_context: tuple[MemoryEntry, ...],
    ) -> tuple[NotBlankStr, list[NotBlankStr]]:
        """Process a single category group for consolidation.

        Synthesizes and stores the summary FIRST, then deletes the
        originals.  This ordering prevents data loss: if synthesis or
        the store call fails (including non-retryable ProviderError),
        no originals are deleted and the caller sees the exception
        without losing any data.

        If the store succeeds but some individual deletes fail, the
        affected originals remain alongside the summary (duplicated
        data, recoverable on the next consolidation pass).  This is
        preferable to the alternative (delete-first) where a synthesis
        failure causes permanent data loss of already-deleted entries.

        Individual delete failures are tolerated best-effort: the loop
        continues, logs the failure, and only successfully-deleted
        entry IDs are returned in ``removed_ids``.

        Args:
            category: The memory category.
            group: Entries in this category.
            agent_id: Owning agent identifier.
            trajectory_context: Distillation entries to include as
                trajectory context in the synthesis prompt (may be
                empty).

        Returns:
            Tuple of (summary_id, removed_ids).
        """
        _, to_remove = self._select_entries(group)

        # Synthesize and store BEFORE deleting so that a synthesis or
        # store failure leaves originals intact (no data loss).
        synthesized, used_llm = await self._synthesize(
            to_remove,
            agent_id=agent_id,
            category=category,
            trajectory_context=trajectory_context,
        )
        tag = _LLM_SYNTHESIZED_TAG if used_llm else _CONCAT_FALLBACK_TAG
        store_request = MemoryStoreRequest(
            category=category,
            content=synthesized,
            metadata=MemoryMetadata(
                source="consolidation",
                tags=("consolidated", tag),
            ),
        )
        new_id = await self._backend.store(agent_id, store_request)

        removed_ids: list[NotBlankStr] = []
        for entry in to_remove:
            try:
                await self._backend.delete(agent_id, entry.id)
            except MemoryError, RecursionError:
                logger.error(
                    LLM_STRATEGY_FALLBACK,
                    agent_id=agent_id,
                    category=category.value,
                    entry_id=entry.id,
                    reason="system_error_in_delete",
                    error_type="system",
                    exc_info=True,
                )
                raise
            except Exception as exc:
                logger.warning(
                    LLM_STRATEGY_FALLBACK,
                    agent_id=agent_id,
                    category=category.value,
                    entry_id=entry.id,
                    reason="delete_failed",
                    error=str(exc),
                    error_type=type(exc).__name__,
                    exc_info=True,
                )
                continue
            removed_ids.append(entry.id)

        return new_id, removed_ids

    async def _synthesize(
        self,
        entries: list[MemoryEntry],
        *,
        agent_id: NotBlankStr,
        category: MemoryCategory,
        trajectory_context: tuple[MemoryEntry, ...],
    ) -> tuple[str, bool]:
        """Synthesize multiple entries into a single summary via LLM.

        The per-entry content is truncated to ``_MAX_ENTRY_INPUT_CHARS``
        before being sent to the LLM to guard against oversized inputs.
        When ``trajectory_context`` is non-empty, distillation entry
        trajectories are included in the system prompt.

        Returns a ``(summary, used_llm)`` pair so the caller can tag
        the stored entry correctly.  ``used_llm`` is ``True`` only when
        the LLM returned non-empty content; any fallback path returns
        ``False``.

        Fallback paths (return ``(fallback, False)``):
            - ``RetryExhaustedError`` (all retries exhausted)
            - Empty or whitespace-only LLM response
            - Unexpected non-``ProviderError`` exception (logged WARNING
              with full traceback)

        Non-retryable ``ProviderError`` subclasses propagate.

        Args:
            entries: Entries to synthesize.
            agent_id: Owning agent for log context.
            category: Memory category for log context.
            trajectory_context: Distillation entries to include as
                context (may be empty).

        Returns:
            ``(summary, used_llm)`` tuple.
        """
        user_content = "\n---\n".join(
            f"[{e.category.value}] {e.content[:_MAX_ENTRY_INPUT_CHARS]}"
            for e in entries
        )
        system_prompt = self._build_system_prompt(trajectory_context)

        try:
            messages = [
                ChatMessage(role=MessageRole.SYSTEM, content=system_prompt),
                ChatMessage(role=MessageRole.USER, content=user_content),
            ]
            response = await self._provider.complete(
                messages,
                self._model,
                config=self._completion_config,
            )
            if response.content and response.content.strip():
                logger.info(
                    LLM_STRATEGY_SYNTHESIZED,
                    agent_id=agent_id,
                    category=category.value,
                    entry_count=len(entries),
                    input_length=len(user_content),
                    output_length=len(response.content),
                    model=self._model,
                    trajectory_context_count=len(trajectory_context),
                )
                return response.content.strip(), True
        except MemoryError, RecursionError:
            logger.error(
                LLM_STRATEGY_FALLBACK,
                agent_id=agent_id,
                category=category.value,
                model=self._model,
                reason="system_error",
                exc_info=True,
            )
            raise
        except RetryExhaustedError as exc:
            # Real-world path: the retry handler wrapped a retryable
            # error after all attempts were exhausted.  Fall back to
            # concatenation so consolidation degrades gracefully.
            logger.warning(
                LLM_STRATEGY_FALLBACK,
                agent_id=agent_id,
                category=category.value,
                entry_count=len(entries),
                model=self._model,
                error=str(exc),
                error_type=type(exc).__name__,
                reason="retry_exhausted",
            )
            return self._fallback_summary(entries), False
        except ProviderError as exc:
            if exc.is_retryable:
                # Fallback for tests and edge configurations that
                # bypass the retry handler and surface a retryable
                # error directly.  In production this is normally
                # wrapped in RetryExhaustedError above.
                logger.warning(
                    LLM_STRATEGY_FALLBACK,
                    agent_id=agent_id,
                    category=category.value,
                    entry_count=len(entries),
                    model=self._model,
                    error=str(exc),
                    error_type=type(exc).__name__,
                    reason="retryable_provider_error",
                )
                return self._fallback_summary(entries), False
            # Non-retryable provider errors (auth, validation, etc.)
            # propagate -- they are bugs the caller must see, not
            # conditions to paper over with a fallback summary.
            raise
        except Exception as exc:
            logger.warning(
                LLM_STRATEGY_FALLBACK,
                agent_id=agent_id,
                category=category.value,
                entry_count=len(entries),
                model=self._model,
                error=str(exc),
                error_type=type(exc).__name__,
                reason="unexpected_error",
                exc_info=True,
            )
            return self._fallback_summary(entries), False

        # Empty / whitespace-only LLM response.
        logger.debug(
            LLM_STRATEGY_FALLBACK,
            agent_id=agent_id,
            category=category.value,
            entry_count=len(entries),
            model=self._model,
            reason="empty_response",
        )
        return self._fallback_summary(entries), False

    def _build_system_prompt(
        self,
        trajectory_context: tuple[MemoryEntry, ...],
    ) -> str:
        """Build the synthesis system prompt with optional trajectory context.

        Args:
            trajectory_context: Distillation entries to embed as
                trajectory context (may be empty).

        Returns:
            The system prompt text.
        """
        if not trajectory_context:
            return _BASE_SYSTEM_PROMPT

        context_lines = ["\nRecent trajectory context (for disambiguation only):"]
        for entry in trajectory_context:
            snippet = entry.content[:_MAX_TRAJECTORY_CHARS_PER_ENTRY]
            context_lines.append(f"- {snippet}")
        return _BASE_SYSTEM_PROMPT + "\n" + "\n".join(context_lines)

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
