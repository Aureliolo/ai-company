"""Budget domain MCP tools.

Covers budget config, cost records, and budget config versions.
"""

from typing import TYPE_CHECKING

from synthorg.meta.mcp.tool_builder import read_tool

if TYPE_CHECKING:
    from synthorg.meta.mcp.registry import MCPToolDef

_PAGINATION = {
    "offset": {"type": "integer", "description": "Pagination offset", "default": 0},
    "limit": {"type": "integer", "description": "Page size", "default": 50},
}

BUDGET_TOOLS: tuple[MCPToolDef, ...] = (
    read_tool("budget", "get_config", "Get the current budget configuration."),
    read_tool(
        "budget",
        "list_records",
        "List cost records with optional filtering.",
        {
            "agent_id": {"type": "string", "description": "Filter by agent ID"},
            "task_id": {"type": "string", "description": "Filter by task ID"},
            **_PAGINATION,
        },
    ),
    read_tool(
        "budget",
        "get_agent_spending",
        "Get spending summary for an agent.",
        {
            "agent_id": {"type": "string", "description": "Agent ID"},
        },
        required=("agent_id",),
    ),
    # --- Budget config versions ---
    read_tool(
        "budget_versions", "list", "List budget configuration versions.", _PAGINATION
    ),
    read_tool(
        "budget_versions",
        "get",
        "Get a specific budget config version.",
        {
            "version_num": {"type": "integer", "description": "Version number (>= 1)"},
        },
        required=("version_num",),
    ),
)
