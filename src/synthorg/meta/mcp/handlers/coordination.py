"""Coordination domain handlers."""

from synthorg.meta.mcp.handlers.common import make_handlers_for_tools

COORDINATION_HANDLERS: dict[str, object] = make_handlers_for_tools(
    (
        "synthorg_coordination_coordinate_task",
        "synthorg_coordination_metrics_list",
        "synthorg_scaling_list_decisions",
        "synthorg_scaling_get_decision",
        "synthorg_scaling_get_config",
        "synthorg_scaling_trigger",
        "synthorg_ceremony_policy_get",
        "synthorg_ceremony_policy_get_resolved",
        "synthorg_ceremony_policy_get_active_strategy",
    )
)
