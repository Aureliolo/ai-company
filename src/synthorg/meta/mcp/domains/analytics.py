"""Analytics domain MCP tools.

Covers analytics, metrics, and reports controllers.
"""

from typing import TYPE_CHECKING

from synthorg.meta.mcp.tool_builder import read_tool

if TYPE_CHECKING:
    from synthorg.meta.mcp.registry import MCPToolDef

_PAGINATION = {
    "offset": {"type": "integer", "description": "Pagination offset", "default": 0},
    "limit": {"type": "integer", "description": "Page size", "default": 50},
}

ANALYTICS_TOOLS: tuple[MCPToolDef, ...] = (
    # --- Analytics ---
    read_tool("analytics", "get_overview", "Get analytics overview dashboard data."),
    read_tool(
        "analytics",
        "get_trends",
        "Get trend data for a metric over time.",
        {
            "period": {
                "type": "string",
                "description": "Time period (daily, weekly, monthly)",
            },
            "metric": {"type": "string", "description": "Metric to analyze"},
        },
    ),
    read_tool(
        "analytics",
        "get_forecast",
        "Get forecasted metrics.",
        {
            "horizon_days": {
                "type": "integer",
                "description": "Forecast horizon in days (1-90)",
                "default": 30,
            },
        },
    ),
    # --- Metrics ---
    read_tool("metrics", "get_current", "Get current system metrics."),
    read_tool(
        "metrics",
        "get_history",
        "Get historical metrics.",
        {
            "metric_name": {"type": "string", "description": "Metric name"},
            "since": {"type": "string", "description": "Start datetime (ISO 8601)"},
            "until": {"type": "string", "description": "End datetime (ISO 8601)"},
        },
    ),
    # --- Reports ---
    read_tool("reports", "list", "List generated reports.", _PAGINATION),
    read_tool(
        "reports",
        "get",
        "Get a report by ID.",
        {
            "report_id": {"type": "string", "description": "Report UUID"},
        },
        required=("report_id",),
    ),
    read_tool(
        "reports",
        "generate",
        "Generate a new report.",
        {
            "report_type": {
                "type": "string",
                "description": "Type of report to generate",
            },
            "parameters": {"type": "object", "description": "Report parameters"},
        },
        required=("report_type",),
    ),
)
