"""Organization domain MCP tools.

Covers company, company versions, departments, teams, and role versions.
"""

from typing import TYPE_CHECKING

from synthorg.meta.mcp.tool_builder import read_tool, write_tool

if TYPE_CHECKING:
    from synthorg.meta.mcp.registry import MCPToolDef

_PAGINATION = {
    "offset": {"type": "integer", "description": "Pagination offset", "default": 0},
    "limit": {"type": "integer", "description": "Page size", "default": 50},
}

ORGANIZATION_TOOLS: tuple[MCPToolDef, ...] = (
    # --- Company ---
    read_tool("company", "get", "Get the company configuration."),
    write_tool(
        "company",
        "update",
        "Update company configuration.",
        {
            "updates": {"type": "object", "description": "Fields to update"},
        },
    ),
    read_tool("company", "list_departments", "List departments in the company."),
    write_tool(
        "company",
        "reorder_departments",
        "Reorder departments.",
        {
            "order": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Department names in order",
            },
        },
        required=("order",),
    ),
    # --- Company versions ---
    read_tool(
        "company_versions", "list", "List company configuration versions.", _PAGINATION
    ),
    read_tool(
        "company_versions",
        "get",
        "Get a specific company config version.",
        {
            "version_num": {"type": "integer", "description": "Version number"},
        },
        required=("version_num",),
    ),
    # --- Departments ---
    read_tool("departments", "list", "List departments with pagination.", _PAGINATION),
    read_tool(
        "departments",
        "get",
        "Get a department by name.",
        {
            "name": {"type": "string", "description": "Department name"},
        },
        required=("name",),
    ),
    write_tool(
        "departments",
        "create",
        "Create a new department.",
        {
            "name": {"type": "string", "description": "Department name"},
            "description": {"type": "string", "description": "Department description"},
        },
        required=("name",),
    ),
    write_tool(
        "departments",
        "update",
        "Update a department.",
        {
            "name": {"type": "string", "description": "Department name"},
            "updates": {"type": "object", "description": "Fields to update"},
        },
        required=("name",),
    ),
    write_tool(
        "departments",
        "delete",
        "Delete a department.",
        {
            "name": {"type": "string", "description": "Department name"},
        },
        required=("name",),
    ),
    read_tool(
        "departments",
        "get_health",
        "Get department health status.",
        {
            "name": {"type": "string", "description": "Department name"},
        },
        required=("name",),
    ),
    # --- Teams ---
    read_tool("teams", "list", "List teams with pagination.", _PAGINATION),
    read_tool(
        "teams",
        "get",
        "Get a team by ID.",
        {
            "team_id": {"type": "string", "description": "Team UUID"},
        },
        required=("team_id",),
    ),
    write_tool(
        "teams",
        "create",
        "Create a new team.",
        {
            "name": {"type": "string", "description": "Team name"},
            "department": {"type": "string", "description": "Parent department"},
        },
        required=("name",),
    ),
    write_tool(
        "teams",
        "update",
        "Update a team.",
        {
            "team_id": {"type": "string", "description": "Team UUID"},
            "updates": {"type": "object", "description": "Fields to update"},
        },
        required=("team_id",),
    ),
    write_tool(
        "teams",
        "delete",
        "Delete a team.",
        {
            "team_id": {"type": "string", "description": "Team UUID"},
        },
        required=("team_id",),
    ),
    # --- Role versions ---
    read_tool(
        "role_versions",
        "list",
        "List role configuration versions.",
        {
            "role_name": {"type": "string", "description": "Role name"},
            **_PAGINATION,
        },
        required=("role_name",),
    ),
    read_tool(
        "role_versions",
        "get",
        "Get a specific role version.",
        {
            "role_name": {"type": "string", "description": "Role name"},
            "version_num": {"type": "integer", "description": "Version number"},
        },
        required=("role_name", "version_num"),
    ),
)
