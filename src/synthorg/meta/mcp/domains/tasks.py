"""Task domain MCP tools.

Covers tasks and activities controllers.
"""

from typing import TYPE_CHECKING

from synthorg.meta.mcp.tool_builder import read_tool, write_tool

if TYPE_CHECKING:
    from synthorg.meta.mcp.registry import MCPToolDef

_PAGINATION = {
    "offset": {"type": "integer", "description": "Pagination offset", "default": 0},
    "limit": {"type": "integer", "description": "Page size", "default": 50},
}

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
            **_PAGINATION,
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
        required=("task_id",),
    ),
    write_tool(
        "tasks",
        "delete",
        "Delete a task.",
        {
            "task_id": {"type": "string", "description": "Task UUID"},
        },
        required=("task_id",),
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
    write_tool(
        "tasks",
        "cancel",
        "Cancel a task with a reason.",
        {
            "task_id": {"type": "string", "description": "Task UUID"},
            "reason": {"type": "string", "description": "Cancellation reason"},
        },
        required=("task_id",),
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
            },
            **_PAGINATION,
        },
    ),
)
