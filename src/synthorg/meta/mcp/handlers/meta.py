"""Meta (self-improvement) domain handlers."""

from synthorg.meta.mcp.handlers.common import make_handlers_for_tools

META_HANDLERS: dict[str, object] = make_handlers_for_tools(
    (
        "synthorg_meta_get_config",
        "synthorg_meta_list_rules",
        "synthorg_meta_list_mcp_tools",
        "synthorg_meta_get_mcp_server_config",
        "synthorg_meta_trigger_cycle",
    )
)
