"""Integrations domain MCP tools.

Covers MCP catalog, OAuth, clients, artifacts, and ontology.
"""

from typing import TYPE_CHECKING

from synthorg.meta.mcp.tool_builder import admin_tool, read_tool, write_tool

if TYPE_CHECKING:
    from synthorg.meta.mcp.registry import MCPToolDef

_PAGINATION = {
    "offset": {"type": "integer", "description": "Pagination offset", "default": 0},
    "limit": {"type": "integer", "description": "Page size", "default": 50},
}

INTEGRATION_TOOLS: tuple[MCPToolDef, ...] = (
    # --- MCP catalog ---
    read_tool(
        "mcp_catalog", "list", "List available MCP server catalog entries.", _PAGINATION
    ),
    read_tool(
        "mcp_catalog",
        "search",
        "Search the MCP catalog.",
        {
            "query": {"type": "string", "description": "Search query"},
        },
        required=("query",),
    ),
    read_tool(
        "mcp_catalog",
        "get",
        "Get an MCP catalog entry by ID.",
        {
            "catalog_id": {"type": "string", "description": "Catalog entry ID"},
        },
        required=("catalog_id",),
    ),
    admin_tool(
        "mcp_catalog",
        "install",
        "Install an MCP server from the catalog.",
        {
            "catalog_id": {"type": "string", "description": "Catalog entry to install"},
        },
        required=("catalog_id",),
    ),
    admin_tool(
        "mcp_catalog",
        "uninstall",
        "Uninstall an MCP server.",
        {
            "install_id": {"type": "string", "description": "Installation ID"},
        },
        required=("install_id",),
    ),
    # --- OAuth ---
    read_tool("oauth", "list_providers", "List configured OAuth providers."),
    admin_tool(
        "oauth",
        "configure_provider",
        "Configure an OAuth provider.",
        {
            "provider": {"type": "string", "description": "Provider name"},
            "config": {"type": "object", "description": "OAuth configuration"},
        },
        required=("provider", "config"),
    ),
    admin_tool(
        "oauth",
        "remove_provider",
        "Remove an OAuth provider.",
        {
            "provider": {"type": "string", "description": "Provider name"},
        },
        required=("provider",),
    ),
    # --- Clients ---
    read_tool("clients", "list", "List API clients.", _PAGINATION),
    read_tool(
        "clients",
        "get",
        "Get an API client by ID.",
        {
            "client_id": {"type": "string", "description": "Client UUID"},
        },
        required=("client_id",),
    ),
    admin_tool(
        "clients",
        "create",
        "Create a new API client.",
        {
            "name": {"type": "string", "description": "Client name"},
        },
        required=("name",),
    ),
    admin_tool(
        "clients",
        "deactivate",
        "Deactivate an API client.",
        {
            "client_id": {"type": "string", "description": "Client UUID"},
        },
        required=("client_id",),
    ),
    read_tool(
        "clients",
        "get_satisfaction",
        "Get client satisfaction score.",
        {
            "client_id": {"type": "string", "description": "Client UUID"},
        },
        required=("client_id",),
    ),
    # --- Artifacts ---
    read_tool(
        "artifacts",
        "list",
        "List artifacts with optional filtering.",
        {
            "task_id": {"type": "string", "description": "Filter by task"},
            "created_by": {"type": "string", "description": "Filter by creator"},
            "type": {"type": "string", "description": "Filter by artifact type"},
            **_PAGINATION,
        },
    ),
    read_tool(
        "artifacts",
        "get",
        "Get an artifact by ID.",
        {
            "artifact_id": {"type": "string", "description": "Artifact UUID"},
        },
        required=("artifact_id",),
    ),
    write_tool(
        "artifacts",
        "create",
        "Create a new artifact.",
        {
            "task_id": {"type": "string", "description": "Associated task"},
            "type": {"type": "string", "description": "Artifact type"},
            "content": {"type": "string", "description": "Artifact content"},
        },
        required=("type",),
    ),
    write_tool(
        "artifacts",
        "delete",
        "Delete an artifact.",
        {
            "artifact_id": {"type": "string", "description": "Artifact UUID"},
        },
        required=("artifact_id",),
    ),
    # --- Ontology ---
    read_tool("ontology", "list_entities", "List ontology entities.", _PAGINATION),
    read_tool(
        "ontology",
        "get_entity",
        "Get an ontology entity by name.",
        {
            "entity_name": {"type": "string", "description": "Entity name"},
        },
        required=("entity_name",),
    ),
    read_tool(
        "ontology",
        "get_relationships",
        "Get relationships for an entity.",
        {
            "entity_name": {"type": "string", "description": "Entity name"},
        },
        required=("entity_name",),
    ),
    read_tool(
        "ontology",
        "search",
        "Search the ontology.",
        {
            "query": {"type": "string", "description": "Search query"},
        },
        required=("query",),
    ),
)
