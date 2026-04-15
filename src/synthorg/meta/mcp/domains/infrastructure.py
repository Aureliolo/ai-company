"""Infrastructure domain MCP tools.

Covers health, settings, providers, backup, audit, events, users,
projects, requests, setup, simulations, template packs, and other
infrastructure controllers.
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

INFRASTRUCTURE_TOOLS: tuple[MCPToolDef, ...] = (
    # --- Health ---
    read_tool("health", "check", "Get service health status."),
    # --- Settings ---
    read_tool("settings", "list", "List all settings.", PAGINATION_PROPERTIES),
    read_tool(
        "settings",
        "get",
        "Get a setting by key.",
        {
            "key": {"type": "string", "description": "Setting key"},
        },
        required=("key",),
    ),
    admin_tool(
        "settings",
        "update",
        "Update a setting.",
        {
            "key": {"type": "string", "description": "Setting key"},
            "value": {"type": "string", "description": "New value"},
        },
        required=("key", "value"),
    ),
    admin_tool(
        "settings",
        "delete",
        "Delete a setting.",
        {
            "key": {"type": "string", "description": "Setting key"},
        },
        required=("key",),
    ),
    # --- Providers ---
    read_tool("providers", "list", "List configured LLM providers."),
    read_tool(
        "providers",
        "get",
        "Get a provider configuration.",
        {
            "provider_name": {"type": "string", "description": "Provider name"},
        },
        required=("provider_name",),
    ),
    read_tool(
        "providers",
        "get_health",
        "Get provider health status.",
        {
            "provider_name": {"type": "string", "description": "Provider name"},
        },
        required=("provider_name",),
    ),
    admin_tool(
        "providers",
        "test_connection",
        "Test connection to a provider.",
        {
            "provider_name": {"type": "string", "description": "Provider name"},
        },
        required=("provider_name",),
    ),
    # --- Backup ---
    admin_tool("backup", "create", "Create a backup."),
    read_tool("backup", "list", "List available backups."),
    read_tool(
        "backup",
        "get",
        "Get backup details.",
        {
            "backup_id": {"type": "string", "description": "Backup UUID"},
        },
        required=("backup_id",),
    ),
    admin_tool(
        "backup",
        "delete",
        "Delete a backup.",
        {
            "backup_id": {"type": "string", "description": "Backup UUID"},
        },
        required=("backup_id",),
    ),
    admin_tool(
        "backup",
        "restore",
        "Restore from a backup.",
        {
            "backup_id": {"type": "string", "description": "Backup UUID to restore"},
        },
        required=("backup_id",),
    ),
    # --- Audit ---
    read_tool(
        "audit",
        "list",
        "List audit log entries.",
        {
            "agent_id": {"type": "string", "description": "Filter by agent"},
            "tool_name": {"type": "string", "description": "Filter by tool"},
            "action_type": {"type": "string", "description": "Filter by action type"},
            "verdict": {"type": "string", "description": "Filter by verdict"},
            "since": {"type": "string", "description": "Start datetime (ISO 8601)"},
            "until": {"type": "string", "description": "End datetime (ISO 8601)"},
            **PAGINATION_PROPERTIES,
        },
    ),
    # --- Events ---
    read_tool(
        "events",
        "list",
        "List system events.",
        {
            "event_type": {"type": "string", "description": "Filter by event type"},
            **PAGINATION_PROPERTIES,
        },
    ),
    # --- Users ---
    read_tool("users", "list", "List users.", PAGINATION_PROPERTIES),
    read_tool(
        "users",
        "get",
        "Get a user by ID.",
        {
            "user_id": {"type": "string", "description": "User UUID"},
        },
        required=("user_id",),
    ),
    admin_tool(
        "users",
        "create",
        "Create a new user.",
        {
            "username": {"type": "string", "description": "Username"},
            "role": {"type": "string", "description": "User role"},
        },
        required=("username", "role"),
    ),
    admin_tool(
        "users",
        "update",
        "Update a user.",
        {
            "user_id": {"type": "string", "description": "User UUID"},
            "updates": {"type": "object", "description": "Fields to update"},
        },
        required=("user_id", "updates"),
    ),
    admin_tool(
        "users",
        "delete",
        "Delete a user.",
        {
            "user_id": {"type": "string", "description": "User UUID"},
        },
        required=("user_id",),
    ),
    # --- Projects ---
    read_tool("projects", "list", "List projects.", PAGINATION_PROPERTIES),
    read_tool(
        "projects",
        "get",
        "Get a project by ID.",
        {
            "project_id": {"type": "string", "description": "Project UUID"},
        },
        required=("project_id",),
    ),
    write_tool(
        "projects",
        "create",
        "Create a new project.",
        {
            "name": {"type": "string", "description": "Project name"},
            "description": {"type": "string", "description": "Project description"},
        },
        required=("name",),
    ),
    write_tool(
        "projects",
        "update",
        "Update a project.",
        {
            "project_id": {"type": "string", "description": "Project UUID"},
            "updates": {"type": "object", "description": "Fields to update"},
        },
        required=("project_id", "updates"),
    ),
    write_tool(
        "projects",
        "delete",
        "Delete a project.",
        {
            "project_id": {"type": "string", "description": "Project UUID"},
        },
        required=("project_id",),
    ),
    # --- Requests ---
    read_tool("requests", "list", "List agent requests.", PAGINATION_PROPERTIES),
    read_tool(
        "requests",
        "get",
        "Get a request by ID.",
        {
            "request_id": {"type": "string", "description": "Request UUID"},
        },
        required=("request_id",),
    ),
    write_tool(
        "requests",
        "create",
        "Create a new request.",
        {
            "type": {"type": "string", "description": "Request type"},
            "content": {"type": "string", "description": "Request content"},
        },
        required=("type", "content"),
    ),
    # --- Setup ---
    read_tool("setup", "get_status", "Get setup wizard status."),
    admin_tool(
        "setup",
        "initialize",
        "Initialize the organization setup.",
        {
            "config": {"type": "object", "description": "Initial configuration"},
        },
    ),
    # --- Simulations ---
    read_tool("simulations", "list", "List simulation runs.", PAGINATION_PROPERTIES),
    read_tool(
        "simulations",
        "get",
        "Get a simulation by ID.",
        {
            "simulation_id": {"type": "string", "description": "Simulation UUID"},
        },
        required=("simulation_id",),
    ),
    write_tool(
        "simulations",
        "create",
        "Create and run a simulation.",
        {
            "scenario": {"type": "string", "description": "Simulation scenario"},
            "parameters": {"type": "object", "description": "Simulation parameters"},
        },
        required=("scenario",),
    ),
    # --- Template packs ---
    read_tool(
        "template_packs",
        "list",
        "List available template packs.",
        PAGINATION_PROPERTIES,
    ),
    read_tool(
        "template_packs",
        "get",
        "Get a template pack by ID.",
        {
            "pack_id": {"type": "string", "description": "Template pack UUID"},
        },
        required=("pack_id",),
    ),
    admin_tool(
        "template_packs",
        "install",
        "Install a template pack.",
        {
            "pack_id": {"type": "string", "description": "Template pack to install"},
        },
        required=("pack_id",),
    ),
    admin_tool(
        "template_packs",
        "uninstall",
        "Uninstall a template pack.",
        {
            "pack_id": {"type": "string", "description": "Template pack UUID"},
        },
        required=("pack_id",),
    ),
    # --- Integration health ---
    read_tool(
        "integration_health", "get_all", "Get health status for all integrations."
    ),
    read_tool(
        "integration_health",
        "get",
        "Get health for a specific integration.",
        {
            "integration_name": {"type": "string", "description": "Integration name"},
        },
        required=("integration_name",),
    ),
)
