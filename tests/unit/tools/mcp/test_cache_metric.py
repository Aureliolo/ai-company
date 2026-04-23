"""Tests for ``synthorg_cache_operations_total`` emission from the MCP cache.

Hit / miss / evict are emitted inline with the existing debug logs
so operators can track hit-rate per ``cache_name="mcp_result"``.
"""

from typing import cast
from unittest.mock import MagicMock

import pytest

from synthorg.tools.base import ToolExecutionResult
from synthorg.tools.mcp import cache as mcp_cache_module
from synthorg.tools.mcp.cache import MCPResultCache

pytestmark = pytest.mark.unit


def _result() -> ToolExecutionResult:
    """Build a minimal ``ToolExecutionResult`` for cache round-trip tests."""
    return cast(
        ToolExecutionResult,
        ToolExecutionResult.model_construct(
            success=True,
            output="ok",
            error=None,
            duration_ms=0.0,
        ),
    )


def test_cache_hit_records_metric(monkeypatch: pytest.MonkeyPatch) -> None:
    recorder = MagicMock()
    monkeypatch.setattr(mcp_cache_module, "record_cache_operation", recorder)

    cache = MCPResultCache(max_size=4, ttl_seconds=60.0)
    cache.put("tool_a", {"q": 1}, _result())

    assert cache.get("tool_a", {"q": 1}) is not None

    hit_calls = [
        c
        for c in recorder.call_args_list
        if c.kwargs.get("outcome") == "hit"
        and c.kwargs.get("cache_name") == "mcp_result"
    ]
    assert len(hit_calls) == 1


def test_cache_miss_records_metric(monkeypatch: pytest.MonkeyPatch) -> None:
    recorder = MagicMock()
    monkeypatch.setattr(mcp_cache_module, "record_cache_operation", recorder)

    cache = MCPResultCache(max_size=4, ttl_seconds=60.0)
    assert cache.get("tool_a", {"q": 1}) is None

    miss_calls = [
        c
        for c in recorder.call_args_list
        if c.kwargs.get("outcome") == "miss"
        and c.kwargs.get("cache_name") == "mcp_result"
    ]
    assert len(miss_calls) == 1


def test_cache_eviction_records_metric(monkeypatch: pytest.MonkeyPatch) -> None:
    recorder = MagicMock()
    monkeypatch.setattr(mcp_cache_module, "record_cache_operation", recorder)

    cache = MCPResultCache(max_size=1, ttl_seconds=60.0)
    cache.put("tool_a", {"q": 1}, _result())
    cache.put("tool_b", {"q": 2}, _result())  # evicts tool_a

    evict_calls = [
        c
        for c in recorder.call_args_list
        if c.kwargs.get("outcome") == "evict"
        and c.kwargs.get("cache_name") == "mcp_result"
    ]
    assert len(evict_calls) == 1
