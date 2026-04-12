"""Reranker cache with TTL and LRU eviction.

Thread-safe in-memory cache for query-specific re-ranking results.
"""

import asyncio
import time
from typing import TYPE_CHECKING

from synthorg.observability import get_logger
from synthorg.observability.events.memory import (
    MEMORY_RERANK_CACHE_HIT,
    MEMORY_RERANK_CACHE_MISS,
)

if TYPE_CHECKING:
    from synthorg.memory.retrieval.models import RetrievalCandidate

logger = get_logger(__name__)

_DEFAULT_TTL_SECONDS = 3600
_DEFAULT_MAX_SIZE = 1000


class RerankerCache:
    """LRU cache with TTL for re-ranked retrieval results.

    Stores ``(candidates, timestamp, last_access)`` triples keyed by
    a hash of the query text and candidate entry IDs.  Expired entries
    are evicted on access; when ``max_size`` is exceeded, the least
    recently accessed entry is evicted.

    Thread-safe via ``asyncio.Lock``.

    Args:
        ttl_seconds: Time-to-live in seconds for cached results.
        max_size: Maximum number of cached entries.
    """

    def __init__(
        self,
        *,
        ttl_seconds: int = _DEFAULT_TTL_SECONDS,
        max_size: int = _DEFAULT_MAX_SIZE,
    ) -> None:
        if ttl_seconds <= 0:
            msg = "ttl_seconds must be positive"
            raise ValueError(msg)
        if max_size <= 0:
            msg = "max_size must be positive"
            raise ValueError(msg)
        self._ttl = ttl_seconds
        self._max_size = max_size
        self._store: dict[
            str,
            tuple[tuple[RetrievalCandidate, ...], float, float],
        ] = {}
        self._lock = asyncio.Lock()

    async def get(
        self,
        key: str,
    ) -> tuple[RetrievalCandidate, ...] | None:
        """Retrieve cached candidates, or ``None`` on miss/expiry.

        Args:
            key: Cache key (hash of query + candidate IDs).

        Returns:
            Cached candidates or ``None``.
        """
        async with self._lock:
            entry = self._store.get(key)
            if entry is None:
                logger.debug(
                    MEMORY_RERANK_CACHE_MISS,
                    key=key[:16],
                )
                return None
            candidates, created_at, _ = entry
            if time.monotonic() - created_at > self._ttl:
                del self._store[key]
                logger.debug(
                    MEMORY_RERANK_CACHE_MISS,
                    key=key[:16],
                    reason="expired",
                )
                return None
            # Update last access time
            self._store[key] = (candidates, created_at, time.monotonic())
            logger.debug(
                MEMORY_RERANK_CACHE_HIT,
                key=key[:16],
            )
            return candidates

    async def put(
        self,
        key: str,
        candidates: tuple[RetrievalCandidate, ...],
    ) -> None:
        """Store re-ranked candidates in the cache.

        Evicts the least recently accessed entry when ``max_size``
        is exceeded.

        Args:
            key: Cache key.
            candidates: Re-ranked candidates to cache.
        """
        async with self._lock:
            now = time.monotonic()
            self._store[key] = (candidates, now, now)
            if len(self._store) > self._max_size:
                self._evict_lru()

    async def invalidate(self, key: str) -> None:
        """Remove a specific key from the cache.

        Args:
            key: Cache key to invalidate.
        """
        async with self._lock:
            self._store.pop(key, None)

    async def clear(self) -> None:
        """Remove all entries from the cache."""
        async with self._lock:
            self._store.clear()

    @property
    def size(self) -> int:
        """Current number of cached entries."""
        return len(self._store)

    def _evict_lru(self) -> None:
        """Evict the least recently accessed entry."""
        if not self._store:
            return
        oldest_key = min(
            self._store,
            key=lambda k: self._store[k][2],  # last_access timestamp
        )
        del self._store[oldest_key]
