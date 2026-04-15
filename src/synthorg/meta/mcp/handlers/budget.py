"""Budget domain handlers."""

from synthorg.meta.mcp.handlers.common import make_handlers_for_tools

BUDGET_HANDLERS: dict[str, object] = make_handlers_for_tools(
    (
        "synthorg_budget_get_config",
        "synthorg_budget_list_records",
        "synthorg_budget_get_agent_spending",
        "synthorg_budget_versions_list",
        "synthorg_budget_versions_get",
    )
)
