"""Analytics domain MCP handlers.

8 tools covering org analytics overview/trends/forecast, current +
historical metrics snapshots, and reports.  The analytics stack is
aggregator-based (``meta/signals/*.py`` + scattered controller logic)
with no single service facade on ``app_state``; every handler returns
``not_supported`` until a dedicated analytics service lands.  Reports
list/get/generate are similarly behind the ``reports`` controller.
"""

from collections.abc import Mapping  # noqa: TC003 -- PEP 649 annotation
from types import MappingProxyType
from typing import Any

from synthorg.meta.mcp.handler_protocol import (
    ToolHandler,  # noqa: TC001 -- PEP 649 annotation
)
from synthorg.meta.mcp.handlers.common import not_supported

_WHY_ANALYTICS = (
    "analytics aggregation is orchestrated inside the engine + meta "
    "signals pipeline; no AnalyticsService facade is on app_state"
)
_WHY_METRICS = (
    "metrics snapshots are computed on demand in controller code; no "
    "MetricsService facade on app_state"
)
_WHY_REPORTS = (
    "report generation lives in the reports controller; no "
    "ReportsService facade on app_state"
)


async def _analytics_get_overview(
    *,
    app_state: Any,  # noqa: ARG001
    arguments: dict[str, Any],  # noqa: ARG001
    actor: Any = None,  # noqa: ARG001
) -> str:
    return not_supported("synthorg_analytics_get_overview", _WHY_ANALYTICS)


async def _analytics_get_trends(
    *,
    app_state: Any,  # noqa: ARG001
    arguments: dict[str, Any],  # noqa: ARG001
    actor: Any = None,  # noqa: ARG001
) -> str:
    return not_supported("synthorg_analytics_get_trends", _WHY_ANALYTICS)


async def _analytics_get_forecast(
    *,
    app_state: Any,  # noqa: ARG001
    arguments: dict[str, Any],  # noqa: ARG001
    actor: Any = None,  # noqa: ARG001
) -> str:
    return not_supported("synthorg_analytics_get_forecast", _WHY_ANALYTICS)


async def _metrics_get_current(
    *,
    app_state: Any,  # noqa: ARG001
    arguments: dict[str, Any],  # noqa: ARG001
    actor: Any = None,  # noqa: ARG001
) -> str:
    return not_supported("synthorg_metrics_get_current", _WHY_METRICS)


async def _metrics_get_history(
    *,
    app_state: Any,  # noqa: ARG001
    arguments: dict[str, Any],  # noqa: ARG001
    actor: Any = None,  # noqa: ARG001
) -> str:
    return not_supported("synthorg_metrics_get_history", _WHY_METRICS)


async def _reports_list(
    *,
    app_state: Any,  # noqa: ARG001
    arguments: dict[str, Any],  # noqa: ARG001
    actor: Any = None,  # noqa: ARG001
) -> str:
    return not_supported("synthorg_reports_list", _WHY_REPORTS)


async def _reports_get(
    *,
    app_state: Any,  # noqa: ARG001
    arguments: dict[str, Any],  # noqa: ARG001
    actor: Any = None,  # noqa: ARG001
) -> str:
    return not_supported("synthorg_reports_get", _WHY_REPORTS)


async def _reports_generate(
    *,
    app_state: Any,  # noqa: ARG001
    arguments: dict[str, Any],  # noqa: ARG001
    actor: Any = None,  # noqa: ARG001
) -> str:
    return not_supported("synthorg_reports_generate", _WHY_REPORTS)


ANALYTICS_HANDLERS: Mapping[str, ToolHandler] = MappingProxyType(
    {
        "synthorg_analytics_get_overview": _analytics_get_overview,
        "synthorg_analytics_get_trends": _analytics_get_trends,
        "synthorg_analytics_get_forecast": _analytics_get_forecast,
        "synthorg_metrics_get_current": _metrics_get_current,
        "synthorg_metrics_get_history": _metrics_get_history,
        "synthorg_reports_list": _reports_list,
        "synthorg_reports_get": _reports_get,
        "synthorg_reports_generate": _reports_generate,
    },
)
