"""Agent domain handlers."""

from synthorg.meta.mcp.handlers.common import make_handlers_for_tools

AGENT_HANDLERS: dict[str, object] = make_handlers_for_tools(
    (
        "synthorg_agents_list",
        "synthorg_agents_get",
        "synthorg_agents_create",
        "synthorg_agents_update",
        "synthorg_agents_delete",
        "synthorg_agents_get_performance",
        "synthorg_agents_get_activity",
        "synthorg_agents_get_history",
        "synthorg_agents_get_health",
        "synthorg_personalities_list",
        "synthorg_personalities_get",
        "synthorg_training_list_sessions",
        "synthorg_training_get_session",
        "synthorg_training_start_session",
        "synthorg_autonomy_get",
        "synthorg_autonomy_update",
        "synthorg_collaboration_get_score",
        "synthorg_collaboration_get_calibration",
    )
)
