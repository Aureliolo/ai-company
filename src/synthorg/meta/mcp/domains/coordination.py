"""Coordination domain MCP tools.

Covers coordination, coordination metrics, and scaling.
"""

from typing import TYPE_CHECKING

from synthorg.meta.mcp.tool_builder import read_tool, write_tool

if TYPE_CHECKING:
    from synthorg.meta.mcp.registry import MCPToolDef

_PAGINATION = {
    "offset": {"type": "integer", "description": "Pagination offset", "default": 0},
    "limit": {"type": "integer", "description": "Page size", "default": 50},
}

COORDINATION_TOOLS: tuple[MCPToolDef, ...] = (
    # --- Task coordination ---
    write_tool(
        "coordination",
        "coordinate_task",
        "Coordinate a task assignment.",
        {
            "task_id": {"type": "string", "description": "Task UUID"},
            "strategy": {"type": "string", "description": "Coordination strategy"},
        },
        required=("task_id",),
    ),
    # --- Coordination metrics ---
    read_tool(
        "coordination_metrics",
        "list",
        "List coordination metric records.",
        {
            "task_id": {"type": "string", "description": "Filter by task"},
            "agent_id": {"type": "string", "description": "Filter by agent"},
            "since": {"type": "string", "description": "Start datetime (ISO 8601)"},
            "until": {"type": "string", "description": "End datetime (ISO 8601)"},
            **_PAGINATION,
        },
    ),
    # --- Scaling ---
    read_tool("scaling", "list_decisions", "List scaling decisions.", _PAGINATION),
    read_tool(
        "scaling",
        "get_decision",
        "Get a scaling decision by ID.",
        {
            "decision_id": {"type": "string", "description": "Decision UUID"},
        },
        required=("decision_id",),
    ),
    read_tool("scaling", "get_config", "Get the current scaling configuration."),
    write_tool(
        "scaling",
        "trigger",
        "Trigger a scaling evaluation.",
        {
            "reason": {
                "type": "string",
                "description": "Reason for triggering scaling",
            },
        },
    ),
    # --- Ceremony policy ---
    read_tool("ceremony_policy", "get", "Get the project-level ceremony policy."),
    read_tool(
        "ceremony_policy",
        "get_resolved",
        "Get resolved ceremony policy for a department.",
        {
            "department": {
                "type": "string",
                "description": "Department name (optional)",
            },
        },
    ),
    read_tool(
        "ceremony_policy", "get_active_strategy", "Get the active ceremony strategy."
    ),
)
