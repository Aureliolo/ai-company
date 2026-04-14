"""Unit tests for meta-loop MCP signal tools."""

import pytest

from synthorg.meta.mcp.server import (
    SERVER_NAME,
    get_server_config,
)
from synthorg.meta.mcp.tools import (
    SIGNAL_TOOLS,
    TOOL_PREFIX,
    get_tool_definitions,
)

pytestmark = pytest.mark.unit


class TestMCPTools:
    """MCP tool definition tests."""

    def test_tool_definitions_not_empty(self) -> None:
        tools = get_tool_definitions()
        assert len(tools) > 0

    def test_all_tools_have_required_fields(self) -> None:
        for tool in SIGNAL_TOOLS:
            assert "name" in tool
            assert "description" in tool
            assert "parameters" in tool
            assert tool["name"].startswith(TOOL_PREFIX)

    def test_tool_names_unique(self) -> None:
        names = [t["name"] for t in SIGNAL_TOOLS]
        assert len(names) == len(set(names))

    def test_nine_tools_defined(self) -> None:
        assert len(SIGNAL_TOOLS) == 9


class TestMCPServer:
    """MCP server config tests."""

    def test_server_name(self) -> None:
        assert SERVER_NAME == "synthorg-signals"

    def test_server_config_structure(self) -> None:
        config = get_server_config()
        assert config["name"] == SERVER_NAME
        assert config["transport"] == "stdio"
        assert config["enabled"] is False
        assert isinstance(config["enabled_tools"], list)
        assert config["tool_count"] == 9
