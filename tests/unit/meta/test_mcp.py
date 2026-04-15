"""Unit tests for the unified MCP API server."""

import pytest

from synthorg.meta.mcp.server import (
    SERVER_NAME,
    get_registry,
    get_server_config,
    reset_singletons,
)

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _reset_server_singletons():
    """Reset server singletons before and after each test."""
    reset_singletons()
    yield
    reset_singletons()


class TestUnifiedServer:
    """Unified synthorg-api server tests."""

    def test_server_name(self) -> None:
        assert SERVER_NAME == "synthorg-api"

    def test_server_config_structure(self) -> None:
        config = get_server_config()
        assert config["name"] == SERVER_NAME
        assert config["transport"] == "stdio"
        assert config["enabled"] is True
        tool_names = config["enabled_tools"]
        assert isinstance(tool_names, list)
        tool_count = config["tool_count"]
        assert isinstance(tool_count, int)
        assert tool_count >= 200
        assert config["tool_prefix"] == "synthorg"

    def test_registry_frozen(self) -> None:
        registry = get_registry()
        assert registry.frozen is True
        assert registry.tool_count >= 200

    def test_all_tool_names_start_with_prefix(self) -> None:
        config = get_server_config()
        tool_names = config["enabled_tools"]
        assert isinstance(tool_names, list)
        for name in tool_names:
            assert isinstance(name, str)
            assert name.startswith("synthorg_")
