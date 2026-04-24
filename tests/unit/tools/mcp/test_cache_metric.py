"""Tests for ``synthorg_cache_operations_total`` emission from the MCP cache.

Hit / miss / evict are emitted inline with the existing debug logs
so operators can track hit-rate per ``cache_name="mcp_result"``.
"""

from collections.abc import Callable
from unittest.mock import MagicMock

import pytest

from synthorg.tools.base import ToolExecutionResult
from synthorg.tools.mcp import cache as mcp_cache_module
from synthorg.tools.mcp.cache import MCPResultCache

pytestmark = pytest.mark.unit


def _result() -> ToolExecutionResult:
    """Build a minimal ``ToolExecutionResult`` for cache round-trip tests."""
    return ToolExecutionResult(content="ok")


@pytest.fixture
def recorder_with_filter(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[MagicMock, Callable[[str], int]]:
    """Install a recording stub for ``record_cache_operation``.

    Returns the ``MagicMock`` plus a helper that counts calls for the
    ``mcp_result`` cache at a given outcome -- the pattern every
    test below needs to read off a single outcome.
    """
    recorder = MagicMock()
    monkeypatch.setattr(mcp_cache_module, "record_cache_operation", recorder)

    def count_for_outcome(outcome: str) -> int:
        return sum(
            1
            for call in recorder.call_args_list
            if call.kwargs.get("outcome") == outcome
            and call.kwargs.get("cache_name") == "mcp_result"
        )

    return recorder, count_for_outcome


def test_cache_hit_records_metric(
    recorder_with_filter: tuple[MagicMock, Callable[[str], int]],
) -> None:
    _recorder, count_for_outcome = recorder_with_filter

    cache = MCPResultCache(max_size=4, ttl_seconds=60.0)
    cache.put("tool_a", {"q": 1}, _result())
    assert cache.get("tool_a", {"q": 1}) is not None

    assert count_for_outcome("hit") == 1


def test_cache_miss_records_metric(
    recorder_with_filter: tuple[MagicMock, Callable[[str], int]],
) -> None:
    _recorder, count_for_outcome = recorder_with_filter

    cache = MCPResultCache(max_size=4, ttl_seconds=60.0)
    assert cache.get("tool_a", {"q": 1}) is None

    assert count_for_outcome("miss") == 1


def test_cache_eviction_records_metric(
    recorder_with_filter: tuple[MagicMock, Callable[[str], int]],
) -> None:
    _recorder, count_for_outcome = recorder_with_filter

    cache = MCPResultCache(max_size=1, ttl_seconds=60.0)
    cache.put("tool_a", {"q": 1}, _result())
    cache.put("tool_b", {"q": 2}, _result())  # evicts tool_a

    assert count_for_outcome("evict") == 1
