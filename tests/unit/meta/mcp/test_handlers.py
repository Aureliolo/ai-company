"""Unit tests for MCP tool handlers."""

import json

import pytest

from synthorg.meta.mcp.domains import build_full_registry
from synthorg.meta.mcp.handlers import build_handler_map
from synthorg.meta.mcp.handlers.common import (
    make_handlers_for_tools,
    make_placeholder_handler,
)
from synthorg.meta.mcp.invoker import MCPToolInvoker

pytestmark = pytest.mark.unit


class TestPlaceholderHandler:
    """Tests for the placeholder handler factory."""

    async def test_returns_not_implemented(self) -> None:
        handler = make_placeholder_handler("synthorg_test_get")
        result = await handler(app_state=None, arguments={})
        body = json.loads(result)
        assert body["status"] == "not_implemented"
        assert body["tool"] == "synthorg_test_get"

    async def test_echoes_arguments(self) -> None:
        handler = make_placeholder_handler("synthorg_test_get")
        result = await handler(app_state=None, arguments={"key": "val"})
        body = json.loads(result)
        assert body["arguments_received"] == {"key": "val"}


class TestMakeHandlersForTools:
    """Tests for batch handler creation."""

    def test_creates_handlers_for_all_tools(self) -> None:
        handlers = make_handlers_for_tools(("tool_a", "tool_b", "tool_c"))
        assert len(handlers) == 3
        assert "tool_a" in handlers
        assert "tool_b" in handlers
        assert "tool_c" in handlers

    async def test_all_handlers_are_callable(self) -> None:
        handlers = make_handlers_for_tools(("tool_a",))
        result = await handlers["tool_a"](app_state=None, arguments={})
        body = json.loads(result)
        assert body["tool"] == "tool_a"


class TestBuildHandlerMap:
    """Tests for the unified handler map builder."""

    def test_builds_handler_map(self) -> None:
        handlers = build_handler_map()
        assert len(handlers) > 100

    def test_no_duplicate_keys(self) -> None:
        # build_handler_map raises ValueError on duplicates
        handlers = build_handler_map()
        assert isinstance(handlers, dict)

    def test_handler_count_matches_tool_count(self) -> None:
        """Every tool should have a matching handler."""
        registry = build_full_registry()
        handlers = build_handler_map()
        tool_names = set(registry.get_names())
        handler_keys = set(handlers.keys())
        missing = tool_names - handler_keys
        assert not missing, f"Tools without handlers: {missing}"

    def test_no_orphan_handlers(self) -> None:
        """Every handler should map to a registered tool."""
        registry = build_full_registry()
        handlers = build_handler_map()
        tool_names = set(registry.get_names())
        handler_keys = set(handlers.keys())
        orphans = handler_keys - tool_names
        assert not orphans, f"Handlers without tools: {orphans}"


class TestEndToEndInvocation:
    """End-to-end test: registry + handlers + invoker."""

    async def test_invoke_placeholder_via_invoker(self) -> None:
        registry = build_full_registry()
        handlers = build_handler_map()
        invoker = MCPToolInvoker(registry, handlers)

        result = await invoker.invoke(
            "synthorg_tasks_list",
            {"offset": 0, "limit": 10},
            app_state=None,
        )
        assert result.is_error is False
        body = json.loads(result.content)
        assert body["status"] == "not_implemented"
        assert body["tool"] == "synthorg_tasks_list"
        assert body["arguments_received"]["offset"] == 0

    async def test_invoke_unknown_tool(self) -> None:
        registry = build_full_registry()
        handlers = build_handler_map()
        invoker = MCPToolInvoker(registry, handlers)

        result = await invoker.invoke(
            "synthorg_nonexistent_tool",
            {},
            app_state=None,
        )
        assert result.is_error is True
