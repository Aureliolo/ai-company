"""LLM-based query-specific re-ranker.

Scores retrieval candidates against the current query using a
small-tier model and re-orders by LLM-assigned ranking.
"""

import builtins
import hashlib
import json
from typing import TYPE_CHECKING

from synthorg.observability import get_logger
from synthorg.observability.events.memory import (
    MEMORY_RERANK_COMPLETE,
    MEMORY_RERANK_FAILED,
)
from synthorg.providers.enums import MessageRole
from synthorg.providers.models import ChatMessage
from synthorg.providers.resilience.errors import RetryExhaustedError

if TYPE_CHECKING:
    from synthorg.core.types import NotBlankStr
    from synthorg.memory.retrieval.models import (
        RetrievalCandidate,
        RetrievalQuery,
    )
    from synthorg.memory.retrieval.reranking.cache import RerankerCache
    from synthorg.providers.protocol import CompletionProvider

logger = get_logger(__name__)

_RERANK_SYSTEM_PROMPT = """\
You are a retrieval re-ranker. Given a query and a list of memory \
candidates, rank them by relevance to the query.

Respond with JSON: {{"ranking": [idx0, idx1, ...]}} where each idx \
is the 0-based index of a candidate in the input list, ordered from \
most to least relevant. Include ALL indices exactly once.
"""

_MAX_CANDIDATE_CONTENT_CHARS = 500


def _build_cache_key(
    query_text: str,
    candidate_ids: tuple[str, ...],
) -> str:
    """Build a deterministic cache key from query + candidate IDs."""
    raw = query_text + "|" + ",".join(sorted(candidate_ids))
    return hashlib.sha256(raw.encode()).hexdigest()


class LLMQuerySpecificReranker:
    """LLM-based query-specific re-ranker.

    Calls a small-tier model to re-rank candidates by query relevance.
    Falls back to original order on any LLM failure.

    Args:
        provider: Completion provider for LLM calls.
        model: Model identifier (small-tier recommended).
        cache: Optional re-ranker cache for amortising cost.
    """

    def __init__(
        self,
        *,
        provider: CompletionProvider,
        model: NotBlankStr,
        cache: RerankerCache | None = None,
    ) -> None:
        self._provider = provider
        self._model = model
        self._cache = cache

    async def rerank(
        self,
        query: RetrievalQuery,
        candidates: tuple[RetrievalCandidate, ...],
    ) -> tuple[RetrievalCandidate, ...]:
        """Re-rank candidates using query-specific LLM scoring.

        Falls back to original order on any failure.

        Args:
            query: The original retrieval query.
            candidates: Post-fusion candidates to re-rank.

        Returns:
            Candidates in re-ordered sequence with updated scores.
        """
        if len(candidates) <= 1:
            return candidates

        # Check cache
        if self._cache is not None:
            cache_key = _build_cache_key(
                query.text,
                tuple(c.entry.id for c in candidates),
            )
            cached = await self._cache.get(cache_key)
            if cached is not None:
                return cached
        else:
            cache_key = ""

        try:
            reranked = await self._rerank_via_llm(query, candidates)
        except builtins.MemoryError, RecursionError:
            raise
        except RetryExhaustedError:
            raise
        except Exception as exc:
            logger.warning(
                MEMORY_RERANK_FAILED,
                error=str(exc),
                candidate_count=len(candidates),
                query_text=query.text[:80],
            )
            return candidates
        else:
            if self._cache is not None and cache_key:
                await self._cache.put(cache_key, reranked)
            logger.info(
                MEMORY_RERANK_COMPLETE,
                candidate_count=len(reranked),
                query_text=query.text[:80],
            )
            return reranked

    async def _rerank_via_llm(
        self,
        query: RetrievalQuery,
        candidates: tuple[RetrievalCandidate, ...],
    ) -> tuple[RetrievalCandidate, ...]:
        """Call LLM for re-ranking decision."""
        candidate_lines = []
        for i, c in enumerate(candidates):
            content_preview = c.entry.content[:_MAX_CANDIDATE_CONTENT_CHARS]
            candidate_lines.append(
                f"[{i}] score={c.combined_score:.2f} content={content_preview!r}",
            )
        user_content = f"Query: {query.text}\n\nCandidates:\n" + "\n".join(
            candidate_lines
        )
        messages: list[ChatMessage] = [
            ChatMessage(
                role=MessageRole.SYSTEM,
                content=_RERANK_SYSTEM_PROMPT,
            ),
            ChatMessage(role=MessageRole.USER, content=user_content),
        ]
        response = await self._provider.complete(messages, self._model)
        if response.content is None:
            logger.debug(
                MEMORY_RERANK_FAILED,
                error="LLM returned null content",
                candidate_count=len(candidates),
            )
            return candidates

        parsed = json.loads(response.content)
        ranking: list[int] = parsed.get("ranking", [])

        # Validate ranking indices
        n = len(candidates)
        if sorted(ranking) != list(range(n)):
            logger.debug(
                MEMORY_RERANK_FAILED,
                error="Invalid ranking indices from LLM",
                expected_count=n,
                received=ranking,
            )
            return candidates

        # Re-order preserving original combined_score so downstream
        # filtering/diversity logic still sees the true relevance signal.
        # The re-ranking intent is communicated via sequence order.
        return tuple(candidates[idx] for idx in ranking)
