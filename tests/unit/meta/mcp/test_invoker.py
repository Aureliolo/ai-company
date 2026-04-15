"""Unit tests for MCP tool invoker."""

import json

import pytest

from synthorg.meta.mcp.invoker import MCPToolInvoker
from synthorg.meta.mcp.registry import DomainToolRegistry, MCPToolDef

pytestmark = pytest.mark.unit


def _make_tool(name: str = "synthorg_test_get") -> MCPToolDef:
    return MCPToolDef(
        name=name,
        description="test",
        parameters={"type": "object", "properties": {}},
        capability="test:read",
        handler_key=name,
    )


def _registry_with(*tools: MCPToolDef) -> DomainToolRegistry:
    registry = DomainToolRegistry()
    for t in tools:
        registry.register(t)
    registry.freeze()
    return registry


class TestMCPToolInvoker:
    """MCPToolInvoker dispatch tests."""

    async def test_invoke_success(self) -> None:
        tool = _make_tool()
        registry = _registry_with(tool)

        async def handler(*, app_state: object, arguments: dict[str, object]) -> str:
            return json.dumps({"result": "ok"})

        invoker = MCPToolInvoker(registry, {"synthorg_test_get": handler})
        result = await invoker.invoke("synthorg_test_get", {}, app_state=None)
        assert result.is_error is False
        assert json.loads(result.content) == {"result": "ok"}

    async def test_invoke_unknown_tool(self) -> None:
        registry = _registry_with()
        invoker = MCPToolInvoker(registry, {})
        result = await invoker.invoke("nonexistent", {}, app_state=None)
        assert result.is_error is True
        body = json.loads(result.content)
        assert "Unknown tool" in body["error"]

    async def test_invoke_no_handler(self) -> None:
        tool = _make_tool()
        registry = _registry_with(tool)
        # Register tool but no handler
        invoker = MCPToolInvoker(registry, {})
        result = await invoker.invoke("synthorg_test_get", {}, app_state=None)
        assert result.is_error is True
        body = json.loads(result.content)
        assert "No handler" in body["error"]

    async def test_invoke_handler_exception(self) -> None:
        tool = _make_tool()
        registry = _registry_with(tool)

        async def bad_handler(
            *, app_state: object, arguments: dict[str, object]
        ) -> str:
            msg = "something broke"
            raise ValueError(msg)

        invoker = MCPToolInvoker(registry, {"synthorg_test_get": bad_handler})
        result = await invoker.invoke("synthorg_test_get", {}, app_state=None)
        assert result.is_error is True
        body = json.loads(result.content)
        assert body["error"] == "ValueError"
        assert "something broke" in body["detail"]

    async def test_invoke_passes_arguments(self) -> None:
        tool = _make_tool()
        registry = _registry_with(tool)
        captured: dict[str, object] = {}

        async def handler(*, app_state: object, arguments: dict[str, object]) -> str:
            captured.update(arguments)
            return json.dumps({"ok": True})

        invoker = MCPToolInvoker(registry, {"synthorg_test_get": handler})
        await invoker.invoke(
            "synthorg_test_get",
            {"key": "value"},
            app_state=None,
        )
        assert captured == {"key": "value"}

    async def test_invoke_passes_app_state(self) -> None:
        tool = _make_tool()
        registry = _registry_with(tool)
        captured: list[object] = []

        async def handler(*, app_state: object, arguments: dict[str, object]) -> str:
            captured.append(app_state)
            return json.dumps({"ok": True})

        sentinel = object()
        invoker = MCPToolInvoker(registry, {"synthorg_test_get": handler})
        await invoker.invoke("synthorg_test_get", {}, app_state=sentinel)
        assert captured[0] is sentinel

    async def test_invoke_handler_key_different_from_name(self) -> None:
        """Tool name and handler_key can differ."""
        tool = MCPToolDef(
            name="synthorg_test_get",
            description="test",
            parameters={"type": "object", "properties": {}},
            capability="test:read",
            handler_key="custom_key",
        )
        registry = _registry_with(tool)

        async def handler(*, app_state: object, arguments: dict[str, object]) -> str:
            return json.dumps({"handler": "custom"})

        invoker = MCPToolInvoker(registry, {"custom_key": handler})
        result = await invoker.invoke("synthorg_test_get", {}, app_state=None)
        assert result.is_error is False
        assert json.loads(result.content) == {"handler": "custom"}
