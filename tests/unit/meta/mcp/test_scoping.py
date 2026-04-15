"""Unit tests for MCP tool capability scoping."""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from synthorg.meta.mcp.scoping import MCPToolScoper, _matches_any
from tests.unit.meta.mcp.conftest import make_tool, registry_with

pytestmark = pytest.mark.unit

# Hypothesis strategies for valid domain/action components
_domain_st = st.from_regex(r"[a-z][a-z0-9_]{0,15}", fullmatch=True)
_action_st = st.from_regex(r"[a-z][a-z0-9_]{0,15}", fullmatch=True)
_capability_st = st.builds(lambda d, a: f"{d}:{a}", _domain_st, _action_st)


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
        t1 = make_tool("synthorg_tasks_list", "tasks:read")
        t2 = make_tool("synthorg_agents_list", "agents:read")
        registry = registry_with(t1, t2)
        scoper = MCPToolScoper(registry)

        result = scoper.visible_tools(("tasks:read",))
        assert len(result) == 1
        assert result[0].name == "synthorg_tasks_list"

    def test_wildcard_domain(self) -> None:
        t1 = make_tool("synthorg_tasks_list", "tasks:read")
        t2 = make_tool("synthorg_tasks_create", "tasks:write")
        t3 = make_tool("synthorg_agents_list", "agents:read")
        registry = registry_with(t1, t2, t3)
        scoper = MCPToolScoper(registry)

        result = scoper.visible_tools(("tasks:*",))
        assert len(result) == 2
        names = {t.name for t in result}
        assert names == {"synthorg_tasks_list", "synthorg_tasks_create"}

    def test_wildcard_action(self) -> None:
        t1 = make_tool("synthorg_tasks_list", "tasks:read")
        t2 = make_tool("synthorg_agents_list", "agents:read")
        t3 = make_tool("synthorg_agents_create", "agents:write")
        registry = registry_with(t1, t2, t3)
        scoper = MCPToolScoper(registry)

        result = scoper.visible_tools(("*:read",))
        assert len(result) == 2
        names = {t.name for t in result}
        assert names == {"synthorg_tasks_list", "synthorg_agents_list"}

    def test_full_wildcard(self) -> None:
        t1 = make_tool("synthorg_tasks_list", "tasks:read")
        t2 = make_tool("synthorg_agents_create", "agents:write")
        registry = registry_with(t1, t2)
        scoper = MCPToolScoper(registry)

        result = scoper.visible_tools(("*",))
        assert len(result) == 2

    def test_denied_overrides_capability(self) -> None:
        t1 = make_tool("synthorg_tasks_list", "tasks:read")
        t2 = make_tool("synthorg_tasks_get", "tasks:read")
        registry = registry_with(t1, t2)
        scoper = MCPToolScoper(registry)

        result = scoper.visible_tools(
            ("tasks:read",),
            denied=("synthorg_tasks_list",),
        )
        assert len(result) == 1
        assert result[0].name == "synthorg_tasks_get"

    def test_denied_overrides_allowed(self) -> None:
        t1 = make_tool("synthorg_tasks_list", "tasks:read")
        registry = registry_with(t1)
        scoper = MCPToolScoper(registry)

        result = scoper.visible_tools(
            (),
            allowed=("synthorg_tasks_list",),
            denied=("synthorg_tasks_list",),
        )
        assert len(result) == 0

    def test_allowed_overrides_no_capability(self) -> None:
        t1 = make_tool("synthorg_tasks_list", "tasks:read")
        registry = registry_with(t1)
        scoper = MCPToolScoper(registry)

        # No capabilities, but explicit allow
        result = scoper.visible_tools(
            (),
            allowed=("synthorg_tasks_list",),
        )
        assert len(result) == 1

    def test_empty_capabilities_returns_nothing(self) -> None:
        t1 = make_tool("synthorg_tasks_list", "tasks:read")
        registry = registry_with(t1)
        scoper = MCPToolScoper(registry)

        result = scoper.visible_tools(())
        assert len(result) == 0

    def test_result_sorted_by_name(self) -> None:
        t1 = make_tool("synthorg_z_tool", "z:read")
        t2 = make_tool("synthorg_a_tool", "a:read")
        registry = registry_with(t1, t2)
        scoper = MCPToolScoper(registry)

        result = scoper.visible_tools(("*",))
        assert result[0].name == "synthorg_a_tool"
        assert result[1].name == "synthorg_z_tool"

    def test_multiple_capabilities(self) -> None:
        t1 = make_tool("synthorg_tasks_list", "tasks:read")
        t2 = make_tool("synthorg_agents_list", "agents:read")
        t3 = make_tool("synthorg_budget_get", "budget:read")
        registry = registry_with(t1, t2, t3)
        scoper = MCPToolScoper(registry)

        result = scoper.visible_tools(("tasks:read", "budget:read"))
        assert len(result) == 2
        names = {t.name for t in result}
        assert names == {"synthorg_tasks_list", "synthorg_budget_get"}

    def test_case_insensitive_denied(self) -> None:
        t1 = make_tool("synthorg_tasks_list", "tasks:read")
        registry = registry_with(t1)
        scoper = MCPToolScoper(registry)

        result = scoper.visible_tools(
            ("tasks:read",),
            denied=("SYNTHORG_TASKS_LIST",),
        )
        assert len(result) == 0

    def test_nonexistent_tool_in_allowed_ignored(self) -> None:
        t1 = make_tool("synthorg_tasks_list", "tasks:read")
        registry = registry_with(t1)
        scoper = MCPToolScoper(registry)

        result = scoper.visible_tools(
            (),
            allowed=("synthorg_phantom_tool",),
        )
        assert len(result) == 0

    def test_nonexistent_tool_in_denied_ignored(self) -> None:
        t1 = make_tool("synthorg_tasks_list", "tasks:read")
        registry = registry_with(t1)
        scoper = MCPToolScoper(registry)

        result = scoper.visible_tools(
            ("tasks:read",),
            denied=("synthorg_phantom_tool",),
        )
        assert len(result) == 1


class TestMatchesAnyProperties:
    """Property-based tests for wildcard matching invariants."""

    @given(capability=_capability_st)
    @settings(max_examples=10, derandomize=True)
    def test_full_wildcard_always_matches(self, capability: str) -> None:
        """The ``*`` pattern matches every valid capability."""
        assert _matches_any(capability, ("*",)) is True

    @given(domain=_domain_st, action=_action_st)
    @settings(max_examples=10, derandomize=True)
    def test_domain_wildcard_matches_same_domain(
        self, domain: str, action: str
    ) -> None:
        """``domain:*`` matches any action in that domain."""
        capability = f"{domain}:{action}"
        assert _matches_any(capability, (f"{domain}:*",)) is True

    @given(domain=_domain_st, action=_action_st)
    @settings(max_examples=10, derandomize=True)
    def test_action_wildcard_matches_same_action(
        self, domain: str, action: str
    ) -> None:
        """``*:action`` matches that action across all domains."""
        capability = f"{domain}:{action}"
        assert _matches_any(capability, (f"*:{action}",)) is True

    @given(capability=_capability_st)
    @settings(max_examples=10, derandomize=True)
    def test_exact_match_is_reflexive(self, capability: str) -> None:
        """A capability always matches itself."""
        assert _matches_any(capability, (capability,)) is True

    @given(capability=_capability_st)
    @settings(max_examples=10, derandomize=True)
    def test_empty_patterns_never_match(self, capability: str) -> None:
        """No patterns means no match."""
        assert _matches_any(capability, ()) is False
