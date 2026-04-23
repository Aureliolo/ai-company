"""Agent domain MCP tools.

Covers agents, personalities, and training controllers.
"""

from typing import TYPE_CHECKING

from synthorg.meta.mcp.tool_builder import (
    PAGINATION_PROPERTIES,
    admin_tool,
    read_tool,
    write_tool,
)

if TYPE_CHECKING:
    from synthorg.meta.mcp.registry import MCPToolDef

_AGENT_NAME = {"agent_name": {"type": "string", "description": "Agent name"}}

AGENT_TOOLS: tuple[MCPToolDef, ...] = (
    # --- Agent CRUD ---
    read_tool(
        "agents", "list", "List all agents with pagination.", PAGINATION_PROPERTIES
    ),
    read_tool(
        "agents",
        "get",
        "Get a single agent by name.",
        _AGENT_NAME,
        required=("agent_name",),
    ),
    write_tool(
        "agents",
        "create",
        "Create a new agent in the organization.",
        {
            "name": {"type": "string", "description": "Agent name"},
            "role": {"type": "string", "description": "Agent role"},
            "department": {"type": "string", "description": "Department name"},
        },
        required=("name", "role", "department"),
    ),
    write_tool(
        "agents",
        "update",
        "Update an existing agent.",
        {
            "agent_name": {"type": "string", "description": "Agent name"},
            "updates": {"type": "object", "description": "Fields to update"},
        },
        required=("agent_name", "updates"),
    ),
    admin_tool(
        "agents",
        "delete",
        "Remove an agent from the organization (destructive; requires confirm).",
        {
            **_AGENT_NAME,
            "reason": {
                "type": "string",
                "description": "Reason for removal (non-blank)",
                "minLength": 1,
            },
            "confirm": {
                "type": "boolean",
                "description": "Must be true to proceed",
                "enum": [True],
            },
        },
        required=("agent_name", "reason", "confirm"),
    ),
    # --- Agent observability ---
    read_tool(
        "agents",
        "get_performance",
        "Get agent performance summary.",
        _AGENT_NAME,
        required=("agent_name",),
    ),
    read_tool(
        "agents",
        "get_activity",
        "Get agent activity feed.",
        {
            **_AGENT_NAME,
            **PAGINATION_PROPERTIES,
        },
        required=("agent_name",),
    ),
    read_tool(
        "agents",
        "get_history",
        "Get agent career history.",
        _AGENT_NAME,
        required=("agent_name",),
    ),
    read_tool(
        "agents",
        "get_health",
        "Get agent health status.",
        _AGENT_NAME,
        required=("agent_name",),
    ),
    # --- Personalities ---
    read_tool(
        "personalities",
        "list",
        "List available personality configurations.",
        PAGINATION_PROPERTIES,
    ),
    read_tool(
        "personalities",
        "get",
        "Get a personality configuration by name.",
        {
            "name": {"type": "string", "description": "Personality name"},
        },
        required=("name",),
    ),
    # --- Training ---
    read_tool(
        "training", "list_sessions", "List training sessions.", PAGINATION_PROPERTIES
    ),
    read_tool(
        "training",
        "get_session",
        "Get a training session by ID.",
        {
            "session_id": {"type": "string", "description": "Training session ID"},
        },
        required=("session_id",),
    ),
    write_tool(
        "training",
        "start_session",
        "Start a new training session for an agent.",
        {
            "agent_name": {"type": "string", "description": "Agent to train"},
        },
        required=("agent_name",),
    ),
    # --- Autonomy ---
    read_tool(
        "autonomy",
        "get",
        "Get autonomy level for an agent.",
        {
            "agent_id": {"type": "string", "description": "Agent ID"},
        },
        required=("agent_id",),
    ),
    admin_tool(
        "autonomy",
        "update",
        "Update autonomy level for an agent.",
        {
            "agent_id": {"type": "string", "description": "Agent ID"},
            "level": {
                "type": "string",
                "description": "New autonomy level",
                "enum": ["NONE", "LIMITED", "SEMI", "FULL"],
            },
        },
        required=("agent_id", "level"),
    ),
    # --- Collaboration ---
    read_tool(
        "collaboration",
        "get_score",
        "Get collaboration score for an agent.",
        {
            "agent_id": {"type": "string", "description": "Agent ID"},
        },
        required=("agent_id",),
    ),
    read_tool(
        "collaboration",
        "get_calibration",
        "Get collaboration calibration data.",
        {
            "agent_id": {"type": "string", "description": "Agent ID"},
        },
        required=("agent_id",),
    ),
)
