"""Retrieval workers -- one per memory scope.

Each worker wraps ``MemoryBackend`` with scope-specific filtering
and scoring.  Workers implement the ``RetrievalWorker`` protocol.
"""

import builtins
import time
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from synthorg.core.enums import MemoryCategory
from synthorg.memory import errors as memory_errors
from synthorg.memory.models import MemoryQuery
from synthorg.memory.ranking import (
    FusionStrategy,
    ScoredMemory,
    fuse_ranked_lists,
    rank_memories,
)
from synthorg.memory.retrieval.models import (
    RetrievalCandidate,
    RetrievalResult,
)
from synthorg.observability import get_logger
from synthorg.observability.events.memory import (
    MEMORY_HIERARCHICAL_WORKER_COMPLETE,
    MEMORY_HIERARCHICAL_WORKER_FAILED,
    MEMORY_HIERARCHICAL_WORKER_START,
)

if TYPE_CHECKING:
    from synthorg.memory.models import MemoryEntry
    from synthorg.memory.protocol import MemoryBackend
    from synthorg.memory.retrieval.models import RetrievalQuery
    from synthorg.memory.retrieval_config import MemoryRetrievalConfig
    from synthorg.memory.shared import SharedKnowledgeStore

logger = get_logger(__name__)

_DEFAULT_EPISODIC_WINDOW_HOURS = 72


def _scored_to_candidate(
    scored: ScoredMemory,
    *,
    source_worker: str,
) -> RetrievalCandidate:
    """Convert a ``ScoredMemory`` to a ``RetrievalCandidate``."""
    return RetrievalCandidate(
        entry=scored.entry,
        relevance_score=scored.relevance_score,
        recency_score=scored.recency_score,
        combined_score=scored.combined_score,
        source_worker=source_worker,
        is_shared=scored.is_shared,
    )


async def _safe_retrieve(
    backend: MemoryBackend,
    agent_id: str,
    query: MemoryQuery,
) -> tuple[MemoryEntry, ...]:
    """Retrieve from backend, returning ``()`` on domain errors.

    Only domain-specific ``MemoryError`` (from ``memory.errors``) is
    swallowed as a non-fatal empty result.  Unexpected exceptions
    propagate so the caller's error isolation captures them.
    """
    try:
        return await backend.retrieve(agent_id, query)
    except builtins.MemoryError, RecursionError:
        raise
    except memory_errors.MemoryError:
        return ()


class SemanticWorker:
    """Full-spectrum semantic worker using RRF or linear ranking.

    Wraps the existing ``MemoryBackend`` dense + optional sparse
    retrieval pipeline.  No category filter -- searches across all
    memory types (same as the flat pipeline).

    Args:
        backend: Memory backend for personal memories.
        config: Retrieval pipeline configuration.
        shared_store: Optional shared knowledge store.
    """

    def __init__(
        self,
        *,
        backend: MemoryBackend,
        config: MemoryRetrievalConfig,
        shared_store: SharedKnowledgeStore | None = None,
    ) -> None:
        self._backend = backend
        self._config = config
        self._shared_store = shared_store

    @property
    def name(self) -> str:
        """Worker identifier."""
        return "semantic"

    async def retrieve(self, query: RetrievalQuery) -> RetrievalResult:
        """Execute semantic retrieval using dense + optional sparse."""
        start = time.monotonic()
        logger.debug(
            MEMORY_HIERARCHICAL_WORKER_START,
            worker=self.name,
            query_text=query.text[:80],
        )
        try:
            mem_query = MemoryQuery(
                text=query.text,
                categories=query.categories,
                limit=query.max_results,
            )
            personal = await _safe_retrieve(
                self._backend,
                query.agent_id,
                mem_query,
            )
            shared: tuple[MemoryEntry, ...] = ()
            if self._shared_store is not None and self._config.include_shared:
                try:
                    shared = await self._shared_store.search_shared(
                        mem_query,
                        exclude_agent=query.agent_id,
                    )
                except builtins.MemoryError, RecursionError:
                    raise
                except Exception as exc:
                    logger.warning(
                        MEMORY_HIERARCHICAL_WORKER_FAILED,
                        worker=self.name,
                        source="shared_store",
                        error=str(exc),
                    )
                    shared = ()

            if self._config.fusion_strategy == FusionStrategy.RRF:
                ranked = self._rank_rrf(
                    personal,
                    shared,
                    max_results=query.max_results,
                )
            else:
                ranked = self._rank_linear(
                    personal,
                    shared,
                    max_results=query.max_results,
                )

            candidates = tuple(
                _scored_to_candidate(s, source_worker=self.name) for s in ranked
            )
            elapsed_ms = int((time.monotonic() - start) * 1000)
            logger.debug(
                MEMORY_HIERARCHICAL_WORKER_COMPLETE,
                worker=self.name,
                candidate_count=len(candidates),
                elapsed_ms=elapsed_ms,
            )
            return RetrievalResult(
                candidates=candidates,
                worker_name=self.name,
                execution_ms=elapsed_ms,
            )
        except builtins.MemoryError, RecursionError:
            raise
        except Exception as exc:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            logger.warning(
                MEMORY_HIERARCHICAL_WORKER_FAILED,
                worker=self.name,
                error=str(exc),
                elapsed_ms=elapsed_ms,
            )
            return RetrievalResult(
                worker_name=self.name,
                execution_ms=elapsed_ms,
                error=str(exc),
            )

    def _rank_rrf(
        self,
        personal: tuple[MemoryEntry, ...],
        shared: tuple[MemoryEntry, ...],
        *,
        max_results: int,
    ) -> tuple[ScoredMemory, ...]:
        """Rank via RRF fusion over personal + shared lists."""
        lists: list[tuple[MemoryEntry, ...]] = []
        if personal:
            lists.append(personal)
        if shared:
            lists.append(shared)
        if not lists:
            return ()
        return fuse_ranked_lists(
            tuple(lists),
            k=self._config.rrf_k,
            max_results=max_results,
        )

    def _rank_linear(
        self,
        personal: tuple[MemoryEntry, ...],
        shared: tuple[MemoryEntry, ...],
        *,
        max_results: int,
    ) -> tuple[ScoredMemory, ...]:
        """Rank via linear combination of relevance + recency."""
        effective_config = self._config.model_copy(
            update={"max_memories": max_results},
        )
        return rank_memories(
            personal,
            config=effective_config,
            now=datetime.now(UTC),
            shared_entries=shared or (),
        )


class EpisodicWorker:
    """Time-windowed episodic memory worker.

    Retrieves recent EPISODIC memories within a configurable time
    window and ranks by recency.

    Args:
        backend: Memory backend for personal memories.
        time_window_hours: Lookback window in hours.
    """

    def __init__(
        self,
        *,
        backend: MemoryBackend,
        time_window_hours: int = _DEFAULT_EPISODIC_WINDOW_HOURS,
    ) -> None:
        self._backend = backend
        self._time_window_hours = time_window_hours

    @property
    def name(self) -> str:
        """Worker identifier."""
        return "episodic"

    async def retrieve(self, query: RetrievalQuery) -> RetrievalResult:
        """Retrieve recent episodic memories."""
        start = time.monotonic()
        logger.debug(
            MEMORY_HIERARCHICAL_WORKER_START,
            worker=self.name,
            query_text=query.text[:80],
        )
        try:
            since = datetime.now(UTC) - timedelta(
                hours=self._time_window_hours,
            )
            mem_query = MemoryQuery(
                text=query.text,
                categories=frozenset({MemoryCategory.EPISODIC}),
                since=since,
                limit=query.max_results,
            )
            entries = await _safe_retrieve(
                self._backend,
                query.agent_id,
                mem_query,
            )
            now = datetime.now(UTC)
            window_seconds = self._time_window_hours * 3600
            candidates_list: list[RetrievalCandidate] = []
            for e in entries:
                relevance = e.relevance_score if e.relevance_score is not None else 0.5
                recency = min(
                    1.0,
                    max(
                        0.0,
                        1.0
                        - (now - e.created_at).total_seconds() / max(window_seconds, 1),
                    ),
                )
                candidates_list.append(
                    RetrievalCandidate(
                        entry=e,
                        relevance_score=relevance,
                        recency_score=recency,
                        combined_score=0.4 * relevance + 0.6 * recency,
                        source_worker=self.name,
                    )
                )
            candidates = tuple(candidates_list)
            elapsed_ms = int((time.monotonic() - start) * 1000)
            logger.debug(
                MEMORY_HIERARCHICAL_WORKER_COMPLETE,
                worker=self.name,
                candidate_count=len(candidates),
                elapsed_ms=elapsed_ms,
            )
            return RetrievalResult(
                candidates=candidates,
                worker_name=self.name,
                execution_ms=elapsed_ms,
            )
        except builtins.MemoryError, RecursionError:
            raise
        except Exception as exc:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            logger.warning(
                MEMORY_HIERARCHICAL_WORKER_FAILED,
                worker=self.name,
                error=str(exc),
                elapsed_ms=elapsed_ms,
            )
            return RetrievalResult(
                worker_name=self.name,
                execution_ms=elapsed_ms,
                error=str(exc),
            )


class ProceduralWorker:
    """Procedural memory worker (skills, how-to patterns).

    Retrieves PROCEDURAL memories filtered by category.

    Args:
        backend: Memory backend for personal memories.
    """

    def __init__(self, *, backend: MemoryBackend) -> None:
        self._backend = backend

    @property
    def name(self) -> str:
        """Worker identifier."""
        return "procedural"

    async def retrieve(self, query: RetrievalQuery) -> RetrievalResult:
        """Retrieve procedural memories."""
        start = time.monotonic()
        logger.debug(
            MEMORY_HIERARCHICAL_WORKER_START,
            worker=self.name,
            query_text=query.text[:80],
        )
        try:
            mem_query = MemoryQuery(
                text=query.text,
                categories=frozenset({MemoryCategory.PROCEDURAL}),
                limit=query.max_results,
            )
            entries = await _safe_retrieve(
                self._backend,
                query.agent_id,
                mem_query,
            )
            candidates = tuple(
                RetrievalCandidate(
                    entry=e,
                    relevance_score=(
                        e.relevance_score if e.relevance_score is not None else 0.5
                    ),
                    combined_score=(
                        e.relevance_score if e.relevance_score is not None else 0.5
                    ),
                    source_worker=self.name,
                )
                for e in entries
            )
            elapsed_ms = int((time.monotonic() - start) * 1000)
            logger.debug(
                MEMORY_HIERARCHICAL_WORKER_COMPLETE,
                worker=self.name,
                candidate_count=len(candidates),
                elapsed_ms=elapsed_ms,
            )
            return RetrievalResult(
                candidates=candidates,
                worker_name=self.name,
                execution_ms=elapsed_ms,
            )
        except builtins.MemoryError, RecursionError:
            raise
        except Exception as exc:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            logger.warning(
                MEMORY_HIERARCHICAL_WORKER_FAILED,
                worker=self.name,
                error=str(exc),
                elapsed_ms=elapsed_ms,
            )
            return RetrievalResult(
                worker_name=self.name,
                execution_ms=elapsed_ms,
                error=str(exc),
            )
