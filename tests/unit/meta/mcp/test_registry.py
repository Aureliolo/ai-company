"""Unit tests for MCP tool registry."""

import pytest
from pydantic import ValidationError

from synthorg.meta.mcp.registry import DomainToolRegistry
from tests.unit.meta.mcp.conftest import make_tool

pytestmark = pytest.mark.unit


class TestMCPToolDef:
    """MCPToolDef model tests."""

    def test_frozen_model(self) -> None:
        tool = make_tool()
        with pytest.raises(ValidationError):
            tool.name = "changed"  # type: ignore[misc]

    def test_required_fields(self) -> None:
        tool = make_tool()
        assert tool.name == "synthorg_test_get"
        assert tool.description == "A test tool"
        assert tool.capability == "test:read"
        assert tool.handler_key == "synthorg_test_get"

    def test_rejects_blank_name(self) -> None:
        with pytest.raises(ValidationError):
            make_tool(name="")

    def test_rejects_blank_description(self) -> None:
        with pytest.raises(ValidationError):
            make_tool(description="")

    def test_rejects_whitespace_name(self) -> None:
        with pytest.raises(ValidationError):
            make_tool(name="   ")

    def test_rejects_name_without_prefix(self) -> None:
        with pytest.raises(ValidationError, match="synthorg_"):
            make_tool(name="invalid_name")

    def test_rejects_bad_capability_format(self) -> None:
        with pytest.raises(ValidationError, match="domain:action"):
            make_tool(capability="no_colon")


class TestDomainToolRegistry:
    """DomainToolRegistry tests."""

    def test_register_and_get(self) -> None:
        registry = DomainToolRegistry()
        tool = make_tool()
        registry.register(tool)
        registry.freeze()
        assert registry.get("synthorg_test_get") is tool

    def test_register_many(self) -> None:
        registry = DomainToolRegistry()
        t1 = make_tool("synthorg_tasks_list")
        t2 = make_tool("synthorg_tasks_get")
        registry.register_many((t1, t2))
        registry.freeze()
        assert registry.tool_count == 2

    def test_duplicate_name_raises(self) -> None:
        registry = DomainToolRegistry()
        registry.register(make_tool("synthorg_test_get"))
        with pytest.raises(ValueError, match="Duplicate tool name"):
            registry.register(make_tool("synthorg_test_get"))

    def test_freeze_prevents_registration(self) -> None:
        registry = DomainToolRegistry()
        registry.freeze()
        with pytest.raises(RuntimeError, match="frozen"):
            registry.register(make_tool())

    def test_freeze_idempotent(self) -> None:
        registry = DomainToolRegistry()
        registry.freeze()
        registry.freeze()  # Should not raise
        assert registry.frozen is True

    def test_auto_freeze_on_get(self) -> None:
        registry = DomainToolRegistry()
        registry.register(make_tool())
        assert registry.frozen is False
        _ = registry.get("synthorg_test_get")
        assert registry.frozen is True

    def test_auto_freeze_on_get_all(self) -> None:
        registry = DomainToolRegistry()
        registry.register(make_tool())
        assert registry.frozen is False
        _ = registry.get_all()
        assert registry.frozen is True

    def test_get_all_sorted(self) -> None:
        registry = DomainToolRegistry()
        registry.register(make_tool("synthorg_z_last"))
        registry.register(make_tool("synthorg_a_first"))
        tools = registry.get_all()
        assert tools[0].name == "synthorg_a_first"
        assert tools[1].name == "synthorg_z_last"

    def test_get_unknown_raises_keyerror(self) -> None:
        registry = DomainToolRegistry()
        registry.freeze()
        with pytest.raises(KeyError):
            registry.get("nonexistent")

    def test_get_tool_definitions_returns_dicts(self) -> None:
        registry = DomainToolRegistry()
        registry.register(make_tool("synthorg_test_one"))
        defs = registry.get_tool_definitions()
        assert len(defs) == 1
        assert defs[0]["name"] == "synthorg_test_one"
        assert "description" in defs[0]
        assert "parameters" in defs[0]
        # Verify no capability or handler_key in the dict
        assert "capability" not in defs[0]
        assert "handler_key" not in defs[0]

    def test_get_names_sorted(self) -> None:
        registry = DomainToolRegistry()
        registry.register(make_tool("synthorg_b_tool"))
        registry.register(make_tool("synthorg_a_tool"))
        names = registry.get_names()
        assert names == ("synthorg_a_tool", "synthorg_b_tool")

    def test_as_mapping_read_only(self) -> None:
        registry = DomainToolRegistry()
        registry.register(make_tool())
        mapping = registry.as_mapping()
        assert "synthorg_test_get" in mapping
        with pytest.raises(TypeError):
            mapping["new"] = make_tool("synthorg_new_tool")  # type: ignore[index]

    def test_tool_count(self) -> None:
        registry = DomainToolRegistry()
        assert registry.tool_count == 0
        registry.register(make_tool("synthorg_one_get"))
        assert registry.tool_count == 1
        registry.register(make_tool("synthorg_two_get"))
        assert registry.tool_count == 2

    def test_empty_registry(self) -> None:
        registry = DomainToolRegistry()
        registry.freeze()
        assert registry.get_all() == ()
        assert registry.get_names() == ()
        assert registry.tool_count == 0
