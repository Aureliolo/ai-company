"""Tests for ``synthorg_cache_operations_total`` emission from the reranker cache.

Hit, miss, and LRU-evict are emitted inline with existing debug
logs so operators can track hit-rate per ``cache_name="reranker"``.
"""

from unittest.mock import MagicMock

import pytest

from synthorg.memory.retrieval.reranking import cache as reranker_cache_module
from synthorg.memory.retrieval.reranking.cache import RerankerCache

pytestmark = pytest.mark.unit


async def test_hit_records_metric(monkeypatch: pytest.MonkeyPatch) -> None:
    recorder = MagicMock()
    monkeypatch.setattr(
        reranker_cache_module,
        "record_cache_operation",
        recorder,
    )

    cache = RerankerCache(ttl_seconds=60, max_size=4)
    await cache.put("k", ("id1", "id2"))
    result = await cache.get("k")
    assert result == ("id1", "id2")

    hit_calls = [
        c
        for c in recorder.call_args_list
        if c.kwargs.get("outcome") == "hit" and c.kwargs.get("cache_name") == "reranker"
    ]
    assert len(hit_calls) == 1


async def test_miss_records_metric(monkeypatch: pytest.MonkeyPatch) -> None:
    recorder = MagicMock()
    monkeypatch.setattr(
        reranker_cache_module,
        "record_cache_operation",
        recorder,
    )

    cache = RerankerCache(ttl_seconds=60, max_size=4)
    result = await cache.get("missing")
    assert result is None

    miss_calls = [
        c
        for c in recorder.call_args_list
        if c.kwargs.get("outcome") == "miss"
        and c.kwargs.get("cache_name") == "reranker"
    ]
    assert len(miss_calls) == 1


async def test_eviction_records_metric(monkeypatch: pytest.MonkeyPatch) -> None:
    recorder = MagicMock()
    monkeypatch.setattr(
        reranker_cache_module,
        "record_cache_operation",
        recorder,
    )

    cache = RerankerCache(ttl_seconds=60, max_size=1)
    await cache.put("a", ("id1",))
    await cache.put("b", ("id2",))  # evicts "a"

    evict_calls = [
        c
        for c in recorder.call_args_list
        if c.kwargs.get("outcome") == "evict"
        and c.kwargs.get("cache_name") == "reranker"
    ]
    assert len(evict_calls) == 1
