"""Signal domain handlers.

Wraps the existing signal aggregation subsystem as MCP tool handlers.
"""

from synthorg.meta.mcp.handlers.common import make_handlers_for_tools

SIGNAL_HANDLERS: dict[str, object] = make_handlers_for_tools(
    (
        "synthorg_signals_get_org_snapshot",
        "synthorg_signals_get_performance",
        "synthorg_signals_get_budget",
        "synthorg_signals_get_coordination",
        "synthorg_signals_get_scaling_history",
        "synthorg_signals_get_error_patterns",
        "synthorg_signals_get_evolution_outcomes",
        "synthorg_signals_get_proposals",
        "synthorg_signals_submit_proposal",
    )
)
