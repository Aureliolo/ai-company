"""Coordination domain MCP tools.

Covers coordination, coordination metrics, and scaling.
"""

from typing import TYPE_CHECKING

from synthorg.meta.mcp.tool_builder import PAGINATION_PROPERTIES, read_tool, write_tool

if TYPE_CHECKING:
    from synthorg.meta.mcp.registry import MCPToolDef

COORDINATION_TOOLS: tuple[MCPToolDef, ...] = (
    # --- Task coordination metrics (read-only lookup) ---
    read_tool(
        "coordination",
        "get_task_metrics",
        (
            "Return the most recent coordination metrics record for a task. "
            "This is a read-only lookup over the metrics store; triggering "
            "coordination is owned by the engine loop and exposed via the "
            "REST endpoint, not MCP."
        ),
        {
            "task_id": {"type": "string", "description": "Task UUID"},
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
            "since": {
                "type": "string",
                "description": "Start datetime (ISO 8601)",
                "format": "date-time",
            },
            "until": {
                "type": "string",
                "description": "End datetime (ISO 8601)",
                "format": "date-time",
            },
            **PAGINATION_PROPERTIES,
        },
    ),
    # --- Scaling ---
    read_tool(
        "scaling", "list_decisions", "List scaling decisions.", PAGINATION_PROPERTIES
    ),
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
        required=("reason",),
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
