"""Tests for ``synthorg_cache_operations_total`` emission from the reranker cache.

Hit, miss, and LRU-evict are emitted inline with existing debug
logs so operators can track hit-rate per ``cache_name="reranker"``.
"""

from unittest.mock import MagicMock, call

import pytest

from synthorg.memory.retrieval.reranking import cache as reranker_cache_module
from synthorg.memory.retrieval.reranking.cache import RerankerCache

pytestmark = pytest.mark.unit


@pytest.fixture
def recorder(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Install a recording stub for ``record_cache_operation``."""
    stub = MagicMock()
    monkeypatch.setattr(reranker_cache_module, "record_cache_operation", stub)
    return stub


async def test_hit_records_metric(recorder: MagicMock) -> None:
    cache = RerankerCache(ttl_seconds=60, max_size=4)
    await cache.put("k", ("id1", "id2"))
    recorder.reset_mock()  # Only the ``get`` below is under test.

    result = await cache.get("k")
    assert result == ("id1", "id2")

    assert recorder.call_args_list == [call(cache_name="reranker", outcome="hit")]


async def test_miss_records_metric(recorder: MagicMock) -> None:
    cache = RerankerCache(ttl_seconds=60, max_size=4)

    result = await cache.get("missing")
    assert result is None

    assert recorder.call_args_list == [call(cache_name="reranker", outcome="miss")]


async def test_eviction_records_metric(recorder: MagicMock) -> None:
    cache = RerankerCache(ttl_seconds=60, max_size=1)
    await cache.put("a", ("id1",))
    recorder.reset_mock()  # Isolate the eviction caused by the next put.

    await cache.put("b", ("id2",))  # evicts "a"

    assert recorder.call_args_list == [call(cache_name="reranker", outcome="evict")]
