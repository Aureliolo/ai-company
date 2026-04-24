"""Tests for ``synthorg_cache_operations_total`` emission from the MCP cache.

Hit / miss / evict are emitted inline with the existing debug logs
so operators can track hit-rate per ``cache_name="mcp_result"``.
"""

from unittest.mock import MagicMock, call

import pytest

from synthorg.tools.base import ToolExecutionResult
from synthorg.tools.mcp import cache as mcp_cache_module
from synthorg.tools.mcp.cache import MCPResultCache

pytestmark = pytest.mark.unit


def _result() -> ToolExecutionResult:
    """Build a minimal ``ToolExecutionResult`` for cache round-trip tests."""
    return ToolExecutionResult(content="ok")


@pytest.fixture
def recorder(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Install a recording stub for ``record_cache_operation``."""
    stub = MagicMock()
    monkeypatch.setattr(mcp_cache_module, "record_cache_operation", stub)
    return stub


def test_cache_hit_records_metric(recorder: MagicMock) -> None:
    cache = MCPResultCache(max_size=4, ttl_seconds=60.0)
    cache.put("tool_a", {"q": 1}, _result())
    recorder.reset_mock()  # Only the ``get`` below is under test.

    assert cache.get("tool_a", {"q": 1}) is not None

    # Exact single call: extra or mislabeled emissions fail the test.
    assert recorder.call_args_list == [call(cache_name="mcp_result", outcome="hit")]


def test_cache_miss_records_metric(recorder: MagicMock) -> None:
    cache = MCPResultCache(max_size=4, ttl_seconds=60.0)

    assert cache.get("tool_a", {"q": 1}) is None

    assert recorder.call_args_list == [call(cache_name="mcp_result", outcome="miss")]


def test_cache_eviction_records_metric(recorder: MagicMock) -> None:
    cache = MCPResultCache(max_size=1, ttl_seconds=60.0)
    cache.put("tool_a", {"q": 1}, _result())
    recorder.reset_mock()  # Isolate the eviction caused by the next put.

    cache.put("tool_b", {"q": 2}, _result())  # evicts tool_a

    assert recorder.call_args_list == [call(cache_name="mcp_result", outcome="evict")]
