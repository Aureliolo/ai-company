"""Meta (self-improvement) domain MCP tools.

Covers the meta controller for the self-improvement cycle.
"""

from typing import TYPE_CHECKING

from synthorg.meta.mcp.tool_builder import admin_tool, read_tool

if TYPE_CHECKING:
    from synthorg.meta.mcp.registry import MCPToolDef

META_TOOLS: tuple[MCPToolDef, ...] = (
    read_tool("meta", "get_config", "Get the self-improvement configuration."),
    read_tool("meta", "list_rules", "List self-improvement rules with their status."),
    read_tool("meta", "list_mcp_tools", "List available MCP tools and descriptions."),
    read_tool(
        "meta", "get_mcp_server_config", "Get MCP server configuration metadata."
    ),
    admin_tool("meta", "trigger_cycle", "Manually trigger a self-improvement cycle."),
)
