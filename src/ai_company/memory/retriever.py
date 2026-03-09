"""Context injection strategy — pre-retrieves and injects memories.

Orchestrates the full retrieval pipeline: backend query → ranking →
budget-fit → format.  Implements ``MemoryInjectionStrategy`` protocol.
"""

import asyncio
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from ai_company.memory import errors as memory_errors
from ai_company.memory.formatter import format_memory_context
from ai_company.memory.injection import (
    DefaultTokenEstimator,
    TokenEstimator,
)
from ai_company.memory.models import MemoryQuery
from ai_company.memory.ranking import rank_memories
from ai_company.observability import get_logger
from ai_company.observability.events.memory import (
    MEMORY_RETRIEVAL_COMPLETE,
    MEMORY_RETRIEVAL_DEGRADED,
    MEMORY_RETRIEVAL_SKIPPED,
    MEMORY_RETRIEVAL_START,
)

if TYPE_CHECKING:
    from ai_company.core.enums import MemoryCategory
    from ai_company.core.types import NotBlankStr
    from ai_company.memory.models import MemoryEntry
    from ai_company.memory.protocol import MemoryBackend
    from ai_company.memory.retrieval_config import MemoryRetrievalConfig
    from ai_company.memory.shared import SharedKnowledgeStore
    from ai_company.providers.models import ChatMessage, ToolDefinition

logger = get_logger(__name__)


async def _safe_retrieve_personal(
    backend: MemoryBackend,
    agent_id: NotBlankStr,
    query: MemoryQuery,
) -> tuple[MemoryEntry, ...]:
    """Retrieve personal memories, returning ``()`` on failure.

    Catches ``memory_errors.MemoryError`` (domain base) and logs
    a degradation warning.  Re-raises ``builtins.MemoryError`` and
    ``RecursionError``.

    Args:
        backend: Memory backend to query.
        agent_id: Agent identifier.
        query: Retrieval query.

    Returns:
        Tuple of retrieved entries, or empty on failure.
    """
    try:
        return await backend.retrieve(agent_id, query)
    except builtins_MemoryError:
        raise
    except RecursionError:
        raise
    except memory_errors.MemoryError:
        logger.warning(
            MEMORY_RETRIEVAL_DEGRADED,
            source="personal",
            agent_id=agent_id,
            exc_info=True,
        )
        return ()
    except Exception:
        logger.error(
            MEMORY_RETRIEVAL_DEGRADED,
            source="personal",
            agent_id=agent_id,
            exc_info=True,
        )
        return ()


async def _safe_retrieve_shared(
    shared_store: SharedKnowledgeStore,
    query: MemoryQuery,
    *,
    exclude_agent: NotBlankStr,
) -> tuple[MemoryEntry, ...]:
    """Retrieve shared memories, returning ``()`` on failure.

    Args:
        shared_store: Shared knowledge store to query.
        query: Retrieval query.
        exclude_agent: Agent ID to exclude from results.

    Returns:
        Tuple of shared entries, or empty on failure.
    """
    try:
        return await shared_store.search_shared(
            query,
            exclude_agent=exclude_agent,
        )
    except builtins_MemoryError:
        raise
    except RecursionError:
        raise
    except memory_errors.MemoryError:
        logger.warning(
            MEMORY_RETRIEVAL_DEGRADED,
            source="shared",
            agent_id=exclude_agent,
            exc_info=True,
        )
        return ()
    except Exception:
        logger.error(
            MEMORY_RETRIEVAL_DEGRADED,
            source="shared",
            agent_id=exclude_agent,
            exc_info=True,
        )
        return ()


# Alias to disambiguate from domain MemoryError
builtins_MemoryError = MemoryError  # noqa: N816


class ContextInjectionStrategy:
    """Context injection strategy — pre-retrieves and injects memories.

    Implements ``MemoryInjectionStrategy`` protocol.  Orchestrates
    the full pipeline: retrieve → rank → budget-fit → format.

    Args:
        backend: Memory backend for personal memories.
        config: Retrieval pipeline configuration.
        shared_store: Optional shared knowledge store.
        token_estimator: Optional custom token estimator.
    """

    def __init__(
        self,
        *,
        backend: MemoryBackend,
        config: MemoryRetrievalConfig,
        shared_store: SharedKnowledgeStore | None = None,
        token_estimator: TokenEstimator | None = None,
    ) -> None:
        self._backend = backend
        self._config = config
        self._shared_store = shared_store
        self._estimator = token_estimator or DefaultTokenEstimator()

    async def prepare_messages(
        self,
        agent_id: NotBlankStr,
        query_text: NotBlankStr,
        token_budget: int,
        *,
        categories: frozenset[MemoryCategory] | None = None,
    ) -> tuple[ChatMessage, ...]:
        """Full pipeline: retrieve → rank → budget-fit → format.

        Returns empty tuple on any failure (graceful degradation).
        Never raises domain memory errors to the caller.
        Re-raises ``builtins.MemoryError`` and ``RecursionError``.

        Args:
            agent_id: The agent requesting memories.
            query_text: Text for semantic retrieval.
            token_budget: Maximum tokens for memory content.
            categories: Optional category filter.

        Returns:
            Tuple of ``ChatMessage`` instances (may be empty).
        """
        logger.info(
            MEMORY_RETRIEVAL_START,
            agent_id=agent_id,
            token_budget=token_budget,
        )

        try:
            return await self._execute_pipeline(
                agent_id=agent_id,
                query_text=query_text,
                token_budget=token_budget,
                categories=categories,
            )
        except builtins_MemoryError:
            raise
        except RecursionError:
            raise
        except memory_errors.MemoryError:
            logger.warning(
                MEMORY_RETRIEVAL_DEGRADED,
                source="pipeline",
                agent_id=agent_id,
                exc_info=True,
            )
            return ()
        except Exception:
            logger.error(
                MEMORY_RETRIEVAL_DEGRADED,
                source="pipeline",
                agent_id=agent_id,
                exc_info=True,
            )
            return ()

    async def _execute_pipeline(
        self,
        *,
        agent_id: NotBlankStr,
        query_text: NotBlankStr,
        token_budget: int,
        categories: frozenset[MemoryCategory] | None,
    ) -> tuple[ChatMessage, ...]:
        """Execute the retrieval → rank → format pipeline.

        Args:
            agent_id: Agent identifier.
            query_text: Semantic search text.
            token_budget: Token budget.
            categories: Category filter.

        Returns:
            Formatted memory messages.
        """
        query = MemoryQuery(
            text=query_text,
            categories=categories,
            limit=self._config.max_memories,
        )

        # Parallel fetch with error isolation
        personal_entries, shared_entries = await self._fetch_memories(
            agent_id=agent_id,
            query=query,
        )

        if not personal_entries and not shared_entries:
            logger.debug(
                MEMORY_RETRIEVAL_SKIPPED,
                agent_id=agent_id,
                reason="no memories found",
            )
            return ()

        now = datetime.now(UTC)
        ranked = rank_memories(
            personal_entries,
            config=self._config,
            now=now,
            shared_entries=shared_entries,
        )

        if not ranked:
            logger.debug(
                MEMORY_RETRIEVAL_SKIPPED,
                agent_id=agent_id,
                reason="all below min_relevance",
            )
            return ()

        result = format_memory_context(
            ranked,
            estimator=self._estimator,
            token_budget=token_budget,
            injection_point=self._config.injection_point,
        )

        logger.info(
            MEMORY_RETRIEVAL_COMPLETE,
            agent_id=agent_id,
            personal_count=len(personal_entries),
            shared_count=len(shared_entries),
            ranked_count=len(ranked),
            messages_produced=len(result),
        )

        return result

    async def _fetch_memories(
        self,
        *,
        agent_id: NotBlankStr,
        query: MemoryQuery,
    ) -> tuple[tuple[MemoryEntry, ...], tuple[MemoryEntry, ...]]:
        """Fetch personal and shared memories in parallel.

        Each fetch is wrapped in error isolation so one failure
        doesn't cancel the other.

        Args:
            agent_id: Agent identifier.
            query: Retrieval query.

        Returns:
            Tuple of (personal_entries, shared_entries).
        """
        should_fetch_shared = (
            self._config.include_shared and self._shared_store is not None
        )

        if should_fetch_shared:
            async with asyncio.TaskGroup() as tg:
                personal_task = tg.create_task(
                    _safe_retrieve_personal(
                        self._backend,
                        agent_id,
                        query,
                    ),
                )
                shared_task = tg.create_task(
                    _safe_retrieve_shared(
                        self._shared_store,  # type: ignore[arg-type]
                        query,
                        exclude_agent=agent_id,
                    ),
                )
            return personal_task.result(), shared_task.result()

        personal = await _safe_retrieve_personal(
            self._backend,
            agent_id,
            query,
        )
        return personal, ()

    def get_tool_definitions(self) -> tuple[ToolDefinition, ...]:
        """Context injection provides no tools.

        Returns:
            Empty tuple.
        """
        return ()

    @property
    def strategy_name(self) -> str:
        """Human-readable strategy identifier.

        Returns:
            ``"context_injection"``.
        """
        return "context_injection"
