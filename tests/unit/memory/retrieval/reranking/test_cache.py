"""Tests for RerankerCache."""

import time
from datetime import UTC, datetime
from unittest.mock import patch

import pytest

from synthorg.core.enums import MemoryCategory
from synthorg.memory.models import MemoryEntry
from synthorg.memory.retrieval.models import RetrievalCandidate
from synthorg.memory.retrieval.reranking.cache import RerankerCache


def _make_candidate(entry_id: str = "mem-1") -> RetrievalCandidate:
    entry = MemoryEntry(
        id=entry_id,
        agent_id="agent-1",
        content="test",
        category=MemoryCategory.SEMANTIC,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    return RetrievalCandidate(
        entry=entry,
        relevance_score=0.8,
        combined_score=0.8,
        source_worker="semantic",
    )


class TestRerankerCache:
    """Tests for RerankerCache."""

    @pytest.mark.unit
    async def test_get_miss(self) -> None:
        cache = RerankerCache()
        result = await cache.get("nonexistent")
        assert result is None

    @pytest.mark.unit
    async def test_put_and_get(self) -> None:
        cache = RerankerCache()
        candidates = (_make_candidate("mem-1"), _make_candidate("mem-2"))
        await cache.put("key1", candidates)
        result = await cache.get("key1")
        assert result is not None
        assert len(result) == 2

    @pytest.mark.unit
    async def test_ttl_expiry(self) -> None:
        cache = RerankerCache(ttl_seconds=1)
        candidates = (_make_candidate(),)
        await cache.put("key1", candidates)

        # Patch time.monotonic to simulate passage of time
        original_monotonic = time.monotonic
        with patch("synthorg.memory.retrieval.reranking.cache.time") as mock_time:
            mock_time.monotonic.return_value = original_monotonic() + 2
            result = await cache.get("key1")
            assert result is None

    @pytest.mark.unit
    async def test_lru_eviction(self) -> None:
        cache = RerankerCache(max_size=2)
        c1 = (_make_candidate("mem-1"),)
        c2 = (_make_candidate("mem-2"),)
        c3 = (_make_candidate("mem-3"),)
        await cache.put("key1", c1)
        await cache.put("key2", c2)
        assert cache.size == 2
        await cache.put("key3", c3)
        assert cache.size == 2
        # key1 should be evicted (oldest)
        result = await cache.get("key1")
        assert result is None

    @pytest.mark.unit
    async def test_invalidate(self) -> None:
        cache = RerankerCache()
        await cache.put("key1", (_make_candidate(),))
        assert cache.size == 1
        await cache.invalidate("key1")
        assert cache.size == 0
        result = await cache.get("key1")
        assert result is None

    @pytest.mark.unit
    async def test_clear(self) -> None:
        cache = RerankerCache()
        await cache.put("key1", (_make_candidate(),))
        await cache.put("key2", (_make_candidate(),))
        assert cache.size == 2
        await cache.clear()
        assert cache.size == 0

    @pytest.mark.unit
    async def test_invalidate_nonexistent(self) -> None:
        cache = RerankerCache()
        await cache.invalidate("nonexistent")
        assert cache.size == 0
