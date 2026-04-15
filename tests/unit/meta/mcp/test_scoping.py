"""Unit tests for MCP tool capability scoping."""

import pytest

from synthorg.meta.mcp.registry import DomainToolRegistry, MCPToolDef
from synthorg.meta.mcp.scoping import MCPToolScoper, _matches_any

pytestmark = pytest.mark.unit


def _make_tool(
    name: str,
    capability: str = "test:read",
) -> MCPToolDef:
    return MCPToolDef(
        name=name,
        description="test",
        parameters={"type": "object", "properties": {}},
        capability=capability,
        handler_key=name,
    )


def _registry_with(*tools: MCPToolDef) -> DomainToolRegistry:
    registry = DomainToolRegistry()
    for t in tools:
        registry.register(t)
    registry.freeze()
    return registry


class TestMatchesAny:
    """Tests for the _matches_any wildcard matcher."""

    def test_exact_match(self) -> None:
        assert _matches_any("tasks:read", ("tasks:read",)) is True

    def test_no_match(self) -> None:
        assert _matches_any("tasks:read", ("agents:read",)) is False

    def test_domain_wildcard(self) -> None:
        assert _matches_any("tasks:read", ("tasks:*",)) is True
        assert _matches_any("tasks:write", ("tasks:*",)) is True

    def test_action_wildcard(self) -> None:
        assert _matches_any("tasks:read", ("*:read",)) is True
        assert _matches_any("agents:read", ("*:read",)) is True
        assert _matches_any("agents:write", ("*:read",)) is False

    def test_full_wildcard(self) -> None:
        assert _matches_any("tasks:read", ("*",)) is True
        assert _matches_any("anything:whatever", ("*",)) is True

    def test_case_insensitive(self) -> None:
        assert _matches_any("Tasks:Read", ("tasks:read",)) is True
        assert _matches_any("tasks:read", ("TASKS:READ",)) is True

    def test_empty_patterns(self) -> None:
        assert _matches_any("tasks:read", ()) is False

    def test_multiple_patterns(self) -> None:
        assert _matches_any("tasks:write", ("agents:read", "tasks:*")) is True

    def test_whitespace_stripped(self) -> None:
        assert _matches_any("  tasks:read  ", ("tasks:read",)) is True
        assert _matches_any("tasks:read", ("  tasks:read  ",)) is True


class TestMCPToolScoper:
    """Tests for MCPToolScoper.visible_tools."""

    def test_exact_capability_match(self) -> None:
        t1 = _make_tool("synthorg_tasks_list", "tasks:read")
        t2 = _make_tool("synthorg_agents_list", "agents:read")
        registry = _registry_with(t1, t2)
        scoper = MCPToolScoper(registry)

        result = scoper.visible_tools(("tasks:read",))
        assert len(result) == 1
        assert result[0].name == "synthorg_tasks_list"

    def test_wildcard_domain(self) -> None:
        t1 = _make_tool("synthorg_tasks_list", "tasks:read")
        t2 = _make_tool("synthorg_tasks_create", "tasks:write")
        t3 = _make_tool("synthorg_agents_list", "agents:read")
        registry = _registry_with(t1, t2, t3)
        scoper = MCPToolScoper(registry)

        result = scoper.visible_tools(("tasks:*",))
        assert len(result) == 2
        names = {t.name for t in result}
        assert names == {"synthorg_tasks_list", "synthorg_tasks_create"}

    def test_wildcard_action(self) -> None:
        t1 = _make_tool("synthorg_tasks_list", "tasks:read")
        t2 = _make_tool("synthorg_agents_list", "agents:read")
        t3 = _make_tool("synthorg_agents_create", "agents:write")
        registry = _registry_with(t1, t2, t3)
        scoper = MCPToolScoper(registry)

        result = scoper.visible_tools(("*:read",))
        assert len(result) == 2
        names = {t.name for t in result}
        assert names == {"synthorg_tasks_list", "synthorg_agents_list"}

    def test_full_wildcard(self) -> None:
        t1 = _make_tool("synthorg_tasks_list", "tasks:read")
        t2 = _make_tool("synthorg_agents_create", "agents:write")
        registry = _registry_with(t1, t2)
        scoper = MCPToolScoper(registry)

        result = scoper.visible_tools(("*",))
        assert len(result) == 2

    def test_denied_overrides_capability(self) -> None:
        t1 = _make_tool("synthorg_tasks_list", "tasks:read")
        t2 = _make_tool("synthorg_tasks_get", "tasks:read")
        registry = _registry_with(t1, t2)
        scoper = MCPToolScoper(registry)

        result = scoper.visible_tools(
            ("tasks:read",),
            denied=("synthorg_tasks_list",),
        )
        assert len(result) == 1
        assert result[0].name == "synthorg_tasks_get"

    def test_denied_overrides_allowed(self) -> None:
        t1 = _make_tool("synthorg_tasks_list", "tasks:read")
        registry = _registry_with(t1)
        scoper = MCPToolScoper(registry)

        result = scoper.visible_tools(
            (),
            allowed=("synthorg_tasks_list",),
            denied=("synthorg_tasks_list",),
        )
        assert len(result) == 0

    def test_allowed_overrides_no_capability(self) -> None:
        t1 = _make_tool("synthorg_tasks_list", "tasks:read")
        registry = _registry_with(t1)
        scoper = MCPToolScoper(registry)

        # No capabilities, but explicit allow
        result = scoper.visible_tools(
            (),
            allowed=("synthorg_tasks_list",),
        )
        assert len(result) == 1

    def test_empty_capabilities_returns_nothing(self) -> None:
        t1 = _make_tool("synthorg_tasks_list", "tasks:read")
        registry = _registry_with(t1)
        scoper = MCPToolScoper(registry)

        result = scoper.visible_tools(())
        assert len(result) == 0

    def test_result_sorted_by_name(self) -> None:
        t1 = _make_tool("synthorg_z_tool", "z:read")
        t2 = _make_tool("synthorg_a_tool", "a:read")
        registry = _registry_with(t1, t2)
        scoper = MCPToolScoper(registry)

        result = scoper.visible_tools(("*",))
        assert result[0].name == "synthorg_a_tool"
        assert result[1].name == "synthorg_z_tool"

    def test_multiple_capabilities(self) -> None:
        t1 = _make_tool("synthorg_tasks_list", "tasks:read")
        t2 = _make_tool("synthorg_agents_list", "agents:read")
        t3 = _make_tool("synthorg_budget_get", "budget:read")
        registry = _registry_with(t1, t2, t3)
        scoper = MCPToolScoper(registry)

        result = scoper.visible_tools(("tasks:read", "budget:read"))
        assert len(result) == 2
        names = {t.name for t in result}
        assert names == {"synthorg_tasks_list", "synthorg_budget_get"}

    def test_case_insensitive_denied(self) -> None:
        t1 = _make_tool("synthorg_tasks_list", "tasks:read")
        registry = _registry_with(t1)
        scoper = MCPToolScoper(registry)

        result = scoper.visible_tools(
            ("tasks:read",),
            denied=("SYNTHORG_TASKS_LIST",),
        )
        assert len(result) == 0

    def test_nonexistent_tool_in_allowed_ignored(self) -> None:
        t1 = _make_tool("synthorg_tasks_list", "tasks:read")
        registry = _registry_with(t1)
        scoper = MCPToolScoper(registry)

        result = scoper.visible_tools(
            (),
            allowed=("synthorg_phantom_tool",),
        )
        assert len(result) == 0

    def test_nonexistent_tool_in_denied_ignored(self) -> None:
        t1 = _make_tool("synthorg_tasks_list", "tasks:read")
        registry = _registry_with(t1)
        scoper = MCPToolScoper(registry)

        result = scoper.visible_tools(
            ("tasks:read",),
            denied=("synthorg_phantom_tool",),
        )
        assert len(result) == 1
