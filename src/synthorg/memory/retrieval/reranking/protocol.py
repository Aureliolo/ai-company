"""Query-specific re-ranker protocol.

Defines the structural interface for post-fusion re-ranking of
retrieval candidates using query-specific scoring.
"""

from typing import Protocol, runtime_checkable

from synthorg.memory.retrieval.models import (
    RetrievalCandidate,  # noqa: TC001
    RetrievalQuery,  # noqa: TC001
)


@runtime_checkable
class QuerySpecificReranker(Protocol):
    """Post-fusion re-ranker using query-specific scoring.

    Takes the top-K fused candidates and scores each against the
    current query using an LLM or other scoring function.  Returns
    candidates in re-ordered sequence with updated combined_scores.
    """

    async def rerank(
        self,
        query: RetrievalQuery,
        candidates: tuple[RetrievalCandidate, ...],
    ) -> tuple[RetrievalCandidate, ...]:
        """Re-rank candidates using query-specific criteria.

        Args:
            query: The original retrieval query.
            candidates: Post-fusion candidates to re-rank.

        Returns:
            Same candidates in re-ordered sequence with updated
            combined_scores reflecting the new ranking.
        """
        ...
