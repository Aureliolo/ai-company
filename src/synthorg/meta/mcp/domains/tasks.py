"""Task domain MCP tools.

Covers tasks and activities controllers.
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

TASK_TOOLS: tuple[MCPToolDef, ...] = (
    # --- Task CRUD ---
    read_tool(
        "tasks",
        "list",
        "List tasks with optional filtering.",
        {
            "status": {"type": "string", "description": "Filter by task status"},
            "assigned_to": {
                "type": "string",
                "description": "Filter by assigned agent",
            },
            "project": {"type": "string", "description": "Filter by project"},
            **PAGINATION_PROPERTIES,
        },
    ),
    read_tool(
        "tasks",
        "get",
        "Get a single task by ID.",
        {
            "task_id": {"type": "string", "description": "Task UUID"},
        },
        required=("task_id",),
    ),
    write_tool(
        "tasks",
        "create",
        "Create a new task.",
        {
            "title": {"type": "string", "description": "Task title"},
            "description": {"type": "string", "description": "Task description"},
            "assigned_to": {"type": "string", "description": "Agent to assign"},
            "project": {"type": "string", "description": "Project name"},
        },
        required=("title",),
    ),
    write_tool(
        "tasks",
        "update",
        "Update an existing task.",
        {
            "task_id": {"type": "string", "description": "Task UUID"},
            "updates": {"type": "object", "description": "Fields to update"},
        },
        required=("task_id", "updates"),
    ),
    admin_tool(
        "tasks",
        "delete",
        "Delete a task (destructive; requires confirm).",
        {
            "task_id": {"type": "string", "description": "Task UUID"},
            "reason": {
                "type": "string",
                "description": "Reason for deletion (non-blank)",
                "minLength": 1,
                "pattern": r".*\S.*",
            },
            "confirm": {
                "type": "boolean",
                "description": "Must be true to proceed",
                "enum": [True],
            },
        },
        required=("task_id", "reason", "confirm"),
    ),
    write_tool(
        "tasks",
        "transition",
        "Transition a task to a new state.",
        {
            "task_id": {"type": "string", "description": "Task UUID"},
            "target_status": {"type": "string", "description": "Target status"},
        },
        required=("task_id", "target_status"),
    ),
    admin_tool(
        "tasks",
        "cancel",
        "Cancel a task (destructive; requires confirm).",
        {
            "task_id": {"type": "string", "description": "Task UUID"},
            "reason": {
                "type": "string",
                "description": "Cancellation reason (non-blank)",
                "minLength": 1,
                "pattern": r".*\S.*",
            },
            "confirm": {
                "type": "boolean",
                "description": "Must be true to proceed",
                "enum": [True],
            },
        },
        required=("task_id", "reason", "confirm"),
    ),
    # --- Activities ---
    read_tool(
        "activities",
        "list",
        "List recent activity events.",
        {
            "type": {"type": "string", "description": "Activity type filter"},
            "agent_id": {"type": "string", "description": "Filter by agent"},
            "last_n_hours": {
                "type": "integer",
                "description": "Lookback hours (24/48/168)",
                "enum": [24, 48, 168],
            },
            **PAGINATION_PROPERTIES,
        },
    ),
)
