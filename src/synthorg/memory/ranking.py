"""Memory ranking — scoring and sorting functions.

All functions are functionally pure (deterministic given the same
inputs).  Logging calls are the only side effect.

``rank_memories`` scores entries via linear combination of relevance
and recency (single-source).  ``fuse_ranked_lists`` merges multiple
pre-ranked lists via Reciprocal Rank Fusion (multi-source).
"""

import math
from enum import StrEnum
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

from synthorg.memory.models import MemoryEntry  # noqa: TC001
from synthorg.observability import get_logger
from synthorg.observability.events.memory import (
    MEMORY_RANKING_COMPLETE,
    MEMORY_RRF_FUSION_COMPLETE,
)

if TYPE_CHECKING:
    from datetime import datetime

    from synthorg.memory.retrieval_config import MemoryRetrievalConfig

logger = get_logger(__name__)


class FusionStrategy(StrEnum):
    """Ranking fusion strategy selection.

    Attributes:
        LINEAR: Weighted linear combination of relevance and recency
            (default, for single-source scoring).
        RRF: Reciprocal Rank Fusion for merging multiple ranked lists
            (for multi-source hybrid search).
    """

    LINEAR = "linear"
    RRF = "rrf"


class ScoredMemory(BaseModel):
    """Memory entry with computed ranking scores.

    Attributes:
        entry: The original memory entry.
        relevance_score: Relevance score — defaults to ``config.default_relevance``
            when the backend omits it, then boosted for personal entries
            (clamped to 1.0).  Shared entries use the unboosted value.
        recency_score: Exponential decay based on age.
        combined_score: Weighted combination of relevance and recency.
        is_shared: Whether this came from SharedKnowledgeStore.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    entry: MemoryEntry = Field(description="The original memory entry")
    relevance_score: float = Field(
        ge=0.0,
        le=1.0,
        description="Relevance score (after boost)",
    )
    recency_score: float = Field(
        ge=0.0,
        le=1.0,
        description="Recency decay score",
    )
    combined_score: float = Field(
        ge=0.0,
        le=1.0,
        description="Weighted combination score",
    )
    is_shared: bool = Field(
        default=False,
        description="Whether from SharedKnowledgeStore",
    )


def compute_recency_score(
    created_at: datetime,
    now: datetime,
    decay_rate: float,
) -> float:
    """Compute exponential recency decay score.

    ``exp(-decay_rate * age_hours)``.  Returns 1.0 for zero age,
    decays toward 0.0 over time.  Future timestamps are clamped to
    1.0.

    Args:
        created_at: When the memory was created.
        now: Current timestamp for age calculation.
        decay_rate: Exponential decay rate per hour.

    Returns:
        Recency score between 0.0 and 1.0.
    """
    age_seconds = (now - created_at).total_seconds()
    if age_seconds <= 0:
        return 1.0
    age_hours = age_seconds / 3600.0
    return math.exp(-decay_rate * age_hours)


def compute_combined_score(
    relevance: float,
    recency: float,
    relevance_weight: float,
    recency_weight: float,
) -> float:
    """Weighted linear combination of relevance and recency.

    Args:
        relevance: Relevance score (0.0-1.0).
        recency: Recency score (0.0-1.0).
        relevance_weight: Weight for relevance.
        recency_weight: Weight for recency.

    Returns:
        Combined score clamped to [0.0, 1.0].  When
        ``relevance_weight + recency_weight == 1.0`` and inputs are
        in [0.0, 1.0], the result is naturally bounded; the clamp
        guards against floating-point tolerance in the weight sum.
    """
    return min(1.0, relevance_weight * relevance + recency_weight * recency)


def _score_entry(
    entry: MemoryEntry,
    *,
    config: MemoryRetrievalConfig,
    now: datetime,
    is_shared: bool,
) -> ScoredMemory:
    """Score a single entry using config weights and decay.

    Personal entries receive ``config.personal_boost`` added to their
    relevance (clamped to 1.0).  Shared entries use raw relevance
    without boost.

    Args:
        entry: The memory entry to score.
        config: Retrieval configuration.
        now: Current timestamp for recency.
        is_shared: Whether this is a shared entry.

    Returns:
        Scored memory with computed scores.
    """
    raw_relevance = (
        entry.relevance_score
        if entry.relevance_score is not None
        else config.default_relevance
    )

    relevance = (
        raw_relevance if is_shared else min(raw_relevance + config.personal_boost, 1.0)
    )

    recency = compute_recency_score(
        entry.created_at,
        now,
        config.recency_decay_rate,
    )

    combined = compute_combined_score(
        relevance,
        recency,
        config.relevance_weight,
        config.recency_weight,
    )

    return ScoredMemory(
        entry=entry,
        relevance_score=relevance,
        recency_score=recency,
        combined_score=combined,
        is_shared=is_shared,
    )


def rank_memories(
    entries: tuple[MemoryEntry, ...],
    *,
    config: MemoryRetrievalConfig,
    now: datetime,
    shared_entries: tuple[MemoryEntry, ...] = (),
) -> tuple[ScoredMemory, ...]:
    """Score, merge, sort, filter, and truncate memory entries.

    1. Score personal entries (with ``personal_boost``).
    2. Score shared entries (no boost).
    3. Merge both sets.
    4. Filter by ``min_relevance`` threshold on ``combined_score``.
    5. Sort descending by ``combined_score``.
    6. Truncate to ``max_memories``.

    Args:
        entries: Personal memory entries.
        config: Retrieval pipeline configuration.
        now: Current timestamp for recency calculations.
        shared_entries: Shared memory entries (no personal boost).

    Returns:
        Sorted and filtered tuple of ``ScoredMemory``.
    """
    scored = [
        _score_entry(entry, config=config, now=now, is_shared=False)
        for entry in entries
    ]
    scored.extend(
        _score_entry(entry, config=config, now=now, is_shared=True)
        for entry in shared_entries
    )

    filtered = [s for s in scored if s.combined_score >= config.min_relevance]
    filtered.sort(key=lambda s: s.combined_score, reverse=True)

    result = tuple(filtered[: config.max_memories])

    logger.debug(
        MEMORY_RANKING_COMPLETE,
        total_candidates=len(scored),
        after_filter=len(filtered),
        after_truncation=len(result),
        min_relevance=config.min_relevance,
        max_memories=config.max_memories,
    )

    return result


def fuse_ranked_lists(
    ranked_lists: tuple[tuple[MemoryEntry, ...], ...],
    *,
    k: int = 60,
    max_results: int = 20,
) -> tuple[ScoredMemory, ...]:
    """Merge multiple pre-ranked lists via Reciprocal Rank Fusion.

    ``RRF_score(doc) = sum(1 / (k + rank_i))`` across all lists
    containing the document.  Scores are min-max normalized to
    [0.0, 1.0].

    For RRF output, only ``combined_score`` is the meaningful
    ranking signal.  ``relevance_score`` preserves the entry's raw
    backend relevance (or 0.0 if absent); ``recency_score`` is 0.0.

    Args:
        ranked_lists: Each inner tuple is a pre-sorted ranked list
            of memory entries (best first).
        k: RRF smoothing constant (default 60).  Smaller values
            amplify rank differences.
        max_results: Maximum entries to return.

    Returns:
        Sorted tuple of ``ScoredMemory`` by descending RRF score.
    """
    # Accumulate raw RRF scores and collect unique entries
    scores: dict[str, float] = {}
    entries: dict[str, MemoryEntry] = {}

    for ranked_list in ranked_lists:
        for rank, entry in enumerate(ranked_list, start=1):
            scores[entry.id] = scores.get(entry.id, 0.0) + 1.0 / (k + rank)
            if entry.id not in entries:
                entries[entry.id] = entry

    if not entries:
        return ()

    # Min-max normalize to [0.0, 1.0]
    min_score = min(scores.values())
    max_score = max(scores.values())
    score_range = max_score - min_score

    normalized = {
        eid: (score - min_score) / score_range if score_range > 0 else 1.0
        for eid, score in scores.items()
    }

    # Build ScoredMemory objects, sort, and truncate
    scored_list: list[ScoredMemory] = []
    for eid, entry in entries.items():
        raw_rel = entry.relevance_score if entry.relevance_score is not None else 0.0
        scored_list.append(
            ScoredMemory(
                entry=entry,
                relevance_score=raw_rel,
                recency_score=0.0,
                combined_score=normalized[eid],
            )
        )
    scored_list.sort(key=lambda s: s.combined_score, reverse=True)

    result = tuple(scored_list[:max_results])

    logger.debug(
        MEMORY_RRF_FUSION_COMPLETE,
        num_lists=len(ranked_lists),
        unique_entries=len(entries),
        after_truncation=len(result),
        k=k,
    )

    return result
