"""Tests for ``synthorg_cache_operations_total`` emission from the reranker cache.

Hit, miss, and LRU-evict are emitted inline with existing debug
logs so operators can track hit-rate per ``cache_name="reranker"``.
"""

from collections.abc import Callable
from unittest.mock import MagicMock

import pytest

from synthorg.memory.retrieval.reranking import cache as reranker_cache_module
from synthorg.memory.retrieval.reranking.cache import RerankerCache

pytestmark = pytest.mark.unit


@pytest.fixture
def recorder_with_filter(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[MagicMock, Callable[[str], int]]:
    """Install a recording stub for ``record_cache_operation``.

    Returns the ``MagicMock`` plus a helper that counts calls for the
    ``reranker`` cache at a given outcome -- the pattern every test
    below needs to read off a single outcome.
    """
    recorder = MagicMock()
    monkeypatch.setattr(reranker_cache_module, "record_cache_operation", recorder)

    def count_for_outcome(outcome: str) -> int:
        return sum(
            1
            for call in recorder.call_args_list
            if call.kwargs.get("outcome") == outcome
            and call.kwargs.get("cache_name") == "reranker"
        )

    return recorder, count_for_outcome


async def test_hit_records_metric(
    recorder_with_filter: tuple[MagicMock, Callable[[str], int]],
) -> None:
    _recorder, count_for_outcome = recorder_with_filter

    cache = RerankerCache(ttl_seconds=60, max_size=4)
    await cache.put("k", ("id1", "id2"))
    result = await cache.get("k")
    assert result == ("id1", "id2")

    assert count_for_outcome("hit") == 1


async def test_miss_records_metric(
    recorder_with_filter: tuple[MagicMock, Callable[[str], int]],
) -> None:
    _recorder, count_for_outcome = recorder_with_filter

    cache = RerankerCache(ttl_seconds=60, max_size=4)
    result = await cache.get("missing")
    assert result is None

    assert count_for_outcome("miss") == 1


async def test_eviction_records_metric(
    recorder_with_filter: tuple[MagicMock, Callable[[str], int]],
) -> None:
    _recorder, count_for_outcome = recorder_with_filter

    cache = RerankerCache(ttl_seconds=60, max_size=1)
    await cache.put("a", ("id1",))
    await cache.put("b", ("id2",))  # evicts "a"

    assert count_for_outcome("evict") == 1
