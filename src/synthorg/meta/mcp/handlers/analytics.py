"""Analytics domain handlers."""

from synthorg.meta.mcp.handlers.common import make_handlers_for_tools

ANALYTICS_HANDLERS: dict[str, object] = make_handlers_for_tools(
    (
        "synthorg_analytics_get_overview",
        "synthorg_analytics_get_trends",
        "synthorg_analytics_get_forecast",
        "synthorg_metrics_get_current",
        "synthorg_metrics_get_history",
        "synthorg_reports_list",
        "synthorg_reports_get",
        "synthorg_reports_generate",
    )
)
