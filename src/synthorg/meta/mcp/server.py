"""MCP signal server setup.

Registers the org signal tools as an internal MCP server
that the Chief of Staff agent connects to. This is the first
slice of the broader API-as-MCP pattern.
"""

from synthorg.meta.mcp.tools import TOOL_PREFIX, get_tool_definitions
from synthorg.observability import get_logger

logger = get_logger(__name__)

# Server metadata.
SERVER_NAME = "synthorg-signals"
SERVER_DESCRIPTION = (
    "Org health signal server for the self-improvement meta-loop. "
    "Provides read access to performance, budget, coordination, "
    "scaling, error, and evolution signals."
)


def get_server_config() -> dict[str, object]:
    """Return MCP server configuration for registration.

    Returns:
        Server config dict compatible with MCPServerConfig.
    """
    tools = get_tool_definitions()
    tool_names = [t["name"] for t in tools]
    return {
        "name": SERVER_NAME,
        "description": SERVER_DESCRIPTION,
        "transport": "stdio",
        "enabled": False,
        "enabled_tools": tool_names,
        "tool_prefix": TOOL_PREFIX,
        "tool_count": len(tools),
    }
