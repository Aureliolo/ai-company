"""Communication domain handlers."""

from synthorg.meta.mcp.handlers.common import make_handlers_for_tools

COMMUNICATION_HANDLERS: dict[str, object] = make_handlers_for_tools(
    (
        "synthorg_messages_list",
        "synthorg_messages_get",
        "synthorg_messages_send",
        "synthorg_messages_delete",
        "synthorg_meetings_list",
        "synthorg_meetings_get",
        "synthorg_meetings_create",
        "synthorg_meetings_update",
        "synthorg_meetings_delete",
        "synthorg_connections_list",
        "synthorg_connections_get",
        "synthorg_connections_create",
        "synthorg_connections_delete",
        "synthorg_connections_check_health",
        "synthorg_webhooks_list",
        "synthorg_webhooks_get",
        "synthorg_webhooks_create",
        "synthorg_webhooks_update",
        "synthorg_webhooks_delete",
        "synthorg_tunnel_get_status",
        "synthorg_tunnel_connect",
    )
)
