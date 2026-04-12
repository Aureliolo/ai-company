"""Default hierarchical retriever -- supervisor-worker orchestration.

Implements the 4-phase pipeline: Route -> Execute -> Merge -> Retry.
"""

import asyncio
import builtins
from typing import TYPE_CHECKING

from synthorg.memory.retrieval.models import (
    FinalRetrievalResult,
    RetrievalCandidate,
    RetrievalResult,
)
from synthorg.observability import get_logger
from synthorg.observability.events.memory import (
    MEMORY_HIERARCHICAL_COMPLETE,
    MEMORY_HIERARCHICAL_MERGE,
    MEMORY_HIERARCHICAL_RETRY,
    MEMORY_HIERARCHICAL_WORKER_FAILED,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from synthorg.memory.retrieval.hierarchical.supervisor import (
        SupervisorRouter,
    )
    from synthorg.memory.retrieval.models import RetrievalQuery
    from synthorg.memory.retrieval.protocol import RetrievalWorker
    from synthorg.memory.retrieval_config import MemoryRetrievalConfig

logger = get_logger(__name__)


def _deduplicate_candidates(
    candidates: tuple[RetrievalCandidate, ...],
    *,
    max_results: int,
) -> tuple[RetrievalCandidate, ...]:
    """Deduplicate by entry.id, keeping highest combined_score."""
    seen: dict[str, RetrievalCandidate] = {}
    for c in candidates:
        existing = seen.get(c.entry.id)
        if existing is None or c.combined_score > existing.combined_score:
            seen[c.entry.id] = c
    sorted_candidates = sorted(
        seen.values(),
        key=lambda c: c.combined_score,
        reverse=True,
    )
    return tuple(sorted_candidates[:max_results])


class DefaultHierarchicalRetriever:
    """Supervisor-worker hierarchical retriever.

    Pipeline:
    1. **Route**: supervisor decides which workers to invoke.
    2. **Execute**: run selected workers in parallel.
    3. **Merge**: deduplicate and sort candidates.
    4. **Retry**: if enabled and result quality is low.

    Args:
        supervisor: LLM-based routing supervisor.
        workers: Mapping from worker name to worker instance.
        config: Retrieval pipeline configuration.
    """

    def __init__(
        self,
        *,
        supervisor: SupervisorRouter,
        workers: Mapping[str, RetrievalWorker],
        config: MemoryRetrievalConfig,
    ) -> None:
        self._supervisor = supervisor
        self._workers = dict(workers)
        self._config = config

    async def retrieve(
        self,
        query: RetrievalQuery,
    ) -> FinalRetrievalResult:
        """Execute the full hierarchical retrieval pipeline."""
        # Phase 1: Route
        routing = await self._supervisor.route(query)
        selected = [name for name in routing.selected_workers if name in self._workers]
        if not selected:
            selected = ["semantic"] if "semantic" in self._workers else []
        if not selected:
            return FinalRetrievalResult()

        # Phase 2: Execute workers in parallel
        worker_results = await self._execute_workers(selected, query)

        # Phase 3: Merge and deduplicate
        all_candidates: list[RetrievalCandidate] = []
        for wr in worker_results:
            all_candidates.extend(wr.candidates)
        merged = _deduplicate_candidates(
            tuple(all_candidates),
            max_results=query.max_results,
        )

        result = FinalRetrievalResult(
            candidates=merged,
            worker_results=tuple(worker_results),
        )

        logger.debug(
            MEMORY_HIERARCHICAL_MERGE,
            total_raw_candidates=len(all_candidates),
            deduped_count=len(merged),
            workers_invoked=selected,
        )

        # Phase 4: Reflective retry
        retries = 0
        if self._supervisor.reflective_retry_enabled:
            max_retries = self._supervisor.max_retry_count
            while retries < max_retries:
                correction = await self._supervisor.evaluate_for_retry(
                    query,
                    result,
                )
                if correction is None:
                    break
                if correction.alternative_strategy == "skip":
                    logger.info(
                        MEMORY_HIERARCHICAL_RETRY,
                        action="skip",
                        retry_count=retries + 1,
                        reason=correction.reason,
                    )
                    break
                retries += 1
                retry_query = (
                    correction.corrected_query
                    if correction.corrected_query is not None
                    else query
                )
                retry_workers = self._resolve_retry_workers(
                    correction.alternative_strategy,
                    selected,
                )
                logger.info(
                    MEMORY_HIERARCHICAL_RETRY,
                    action="executing",
                    retry_count=retries,
                    workers=retry_workers,
                    reason=correction.reason,
                )
                retry_results = await self._execute_workers(
                    retry_workers,
                    retry_query,
                )
                # Merge retry results with existing
                for wr in retry_results:
                    all_candidates.extend(wr.candidates)
                merged = _deduplicate_candidates(
                    tuple(all_candidates),
                    max_results=query.max_results,
                )
                all_worker_results = list(result.worker_results)
                all_worker_results.extend(retry_results)
                result = FinalRetrievalResult(
                    candidates=merged,
                    worker_results=tuple(all_worker_results),
                    retries_performed=retries,
                )

        logger.info(
            MEMORY_HIERARCHICAL_COMPLETE,
            candidate_count=len(result.candidates),
            worker_count=len(result.worker_results),
            retries=retries,
        )
        return result

    async def _execute_workers(
        self,
        worker_names: list[str],
        query: RetrievalQuery,
    ) -> list[RetrievalResult]:
        """Execute named workers in parallel with error isolation."""

        async def _run_worker(name: str) -> RetrievalResult:
            worker = self._workers[name]
            try:
                return await worker.retrieve(query)
            except builtins.MemoryError, RecursionError:
                raise
            except Exception as exc:
                logger.warning(
                    MEMORY_HIERARCHICAL_WORKER_FAILED,
                    worker=name,
                    error=str(exc),
                )
                return RetrievalResult(
                    worker_name=name,
                    error=str(exc),
                )

        async with asyncio.TaskGroup() as tg:
            tasks = [tg.create_task(_run_worker(n)) for n in worker_names]

        return [t.result() for t in tasks]

    def _resolve_retry_workers(
        self,
        alternative_strategy: str | None,
        original_workers: list[str],
    ) -> list[str]:
        """Resolve which workers to use for a retry."""
        if alternative_strategy == "semantic_only":
            return ["semantic"] if "semantic" in self._workers else original_workers
        if alternative_strategy == "episodic_only":
            return ["episodic"] if "episodic" in self._workers else original_workers
        return original_workers
