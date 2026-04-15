"""Budget domain MCP tools.

Covers budget config, cost records, and budget config versions.
"""

from typing import TYPE_CHECKING

from synthorg.meta.mcp.tool_builder import PAGINATION_PROPERTIES, read_tool

if TYPE_CHECKING:
    from synthorg.meta.mcp.registry import MCPToolDef

BUDGET_TOOLS: tuple[MCPToolDef, ...] = (
    read_tool("budget", "get_config", "Get the current budget configuration."),
    read_tool(
        "budget",
        "list_records",
        "List cost records with optional filtering.",
        {
            "agent_id": {"type": "string", "description": "Filter by agent ID"},
            "task_id": {"type": "string", "description": "Filter by task ID"},
            **PAGINATION_PROPERTIES,
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
        "budget_versions",
        "list",
        "List budget configuration versions.",
        PAGINATION_PROPERTIES,
    ),
    read_tool(
        "budget_versions",
        "get",
        "Get a specific budget config version.",
        {
            "version_num": {
                "type": "integer",
                "description": "Version number",
                "minimum": 1,
            },
        },
        required=("version_num",),
    ),
)
