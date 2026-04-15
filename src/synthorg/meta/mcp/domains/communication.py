"""Communication domain MCP tools.

Covers messages, meetings, connections, webhooks, and tunnel.
"""

from typing import TYPE_CHECKING

from synthorg.meta.mcp.tool_builder import admin_tool, read_tool, write_tool

if TYPE_CHECKING:
    from synthorg.meta.mcp.registry import MCPToolDef

_PAGINATION = {
    "offset": {"type": "integer", "description": "Pagination offset", "default": 0},
    "limit": {"type": "integer", "description": "Page size", "default": 50},
}

COMMUNICATION_TOOLS: tuple[MCPToolDef, ...] = (
    # --- Messages ---
    read_tool(
        "messages",
        "list",
        "List messages with optional filtering.",
        {
            "channel": {"type": "string", "description": "Filter by channel"},
            "sender": {"type": "string", "description": "Filter by sender"},
            **_PAGINATION,
        },
    ),
    read_tool(
        "messages",
        "get",
        "Get a message by ID.",
        {
            "message_id": {"type": "string", "description": "Message UUID"},
        },
        required=("message_id",),
    ),
    write_tool(
        "messages",
        "send",
        "Send a new message.",
        {
            "channel": {"type": "string", "description": "Target channel"},
            "content": {"type": "string", "description": "Message content"},
            "sender": {"type": "string", "description": "Sender name"},
        },
        required=("channel", "content"),
    ),
    write_tool(
        "messages",
        "delete",
        "Delete a message.",
        {
            "message_id": {"type": "string", "description": "Message UUID"},
        },
        required=("message_id",),
    ),
    # --- Meetings ---
    read_tool("meetings", "list", "List meeting records.", _PAGINATION),
    read_tool(
        "meetings",
        "get",
        "Get a meeting record by ID.",
        {
            "meeting_id": {"type": "string", "description": "Meeting UUID"},
        },
        required=("meeting_id",),
    ),
    write_tool(
        "meetings",
        "create",
        "Create a meeting record.",
        {
            "title": {"type": "string", "description": "Meeting title"},
            "participants": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Participant names",
            },
        },
        required=("title",),
    ),
    write_tool(
        "meetings",
        "update",
        "Update a meeting record.",
        {
            "meeting_id": {"type": "string", "description": "Meeting UUID"},
            "updates": {"type": "object", "description": "Fields to update"},
        },
        required=("meeting_id",),
    ),
    write_tool(
        "meetings",
        "delete",
        "Delete a meeting record.",
        {
            "meeting_id": {"type": "string", "description": "Meeting UUID"},
        },
        required=("meeting_id",),
    ),
    # --- Connections ---
    read_tool("connections", "list", "List external connections."),
    read_tool(
        "connections",
        "get",
        "Get a connection by name.",
        {
            "name": {"type": "string", "description": "Connection name"},
        },
        required=("name",),
    ),
    admin_tool(
        "connections",
        "create",
        "Create a new external connection.",
        {
            "name": {"type": "string", "description": "Connection name"},
            "connection_type": {"type": "string", "description": "Connection type"},
            "credentials": {"type": "object", "description": "Connection credentials"},
        },
        required=("name", "connection_type"),
    ),
    admin_tool(
        "connections",
        "delete",
        "Delete an external connection.",
        {
            "name": {"type": "string", "description": "Connection name"},
        },
        required=("name",),
    ),
    read_tool(
        "connections",
        "check_health",
        "Check health of a connection.",
        {
            "name": {"type": "string", "description": "Connection name"},
        },
        required=("name",),
    ),
    # --- Webhooks ---
    read_tool("webhooks", "list", "List registered webhooks.", _PAGINATION),
    read_tool(
        "webhooks",
        "get",
        "Get a webhook by ID.",
        {
            "webhook_id": {"type": "string", "description": "Webhook UUID"},
        },
        required=("webhook_id",),
    ),
    admin_tool(
        "webhooks",
        "create",
        "Create a new webhook.",
        {
            "url": {"type": "string", "description": "Webhook URL"},
            "events": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Event types to subscribe",
            },
        },
        required=("url", "events"),
    ),
    admin_tool(
        "webhooks",
        "update",
        "Update a webhook configuration.",
        {
            "webhook_id": {"type": "string", "description": "Webhook UUID"},
            "updates": {"type": "object", "description": "Fields to update"},
        },
        required=("webhook_id",),
    ),
    admin_tool(
        "webhooks",
        "delete",
        "Delete a webhook.",
        {
            "webhook_id": {"type": "string", "description": "Webhook UUID"},
        },
        required=("webhook_id",),
    ),
    # --- Tunnel ---
    read_tool("tunnel", "get_status", "Get tunnel connection status."),
    admin_tool(
        "tunnel",
        "connect",
        "Establish a tunnel connection.",
        {
            "target": {"type": "string", "description": "Tunnel target endpoint"},
        },
        required=("target",),
    ),
)
