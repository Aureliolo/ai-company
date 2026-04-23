"""Analytics domain MCP handlers.

8 tools covering org analytics overview/trends/forecast, current +
historical metrics snapshots, and reports.  The analytics stack is
aggregator-based (``meta/signals/*.py`` + scattered controller logic)
with no single service facade on ``app_state``; every handler returns
``service_fallback`` via the shared :func:`_mk` factory until a dedicated
analytics service lands.  Reports list/get/generate are similarly
behind the ``reports`` controller.
"""

import copy
from collections.abc import Mapping  # noqa: TC003 -- PEP 649 annotation
from types import MappingProxyType
from typing import TYPE_CHECKING, Any

from synthorg.meta.mcp.handler_protocol import (
    ToolHandler,  # noqa: TC001 -- PEP 649 annotation
)
from synthorg.meta.mcp.handlers.common import service_fallback
from synthorg.observability import get_logger

if TYPE_CHECKING:
    from synthorg.core.agent import AgentIdentity

logger = get_logger(__name__)

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


def _mk(tool: str, why: str) -> ToolHandler:
    """Build a ``service_fallback`` handler with ToolHandler-conformant typing."""

    async def handler(
        *,
        app_state: Any,  # noqa: ARG001
        arguments: dict[str, Any],  # noqa: ARG001
        actor: AgentIdentity | None = None,  # noqa: ARG001
    ) -> str:
        return service_fallback(tool, why)

    return handler


ANALYTICS_HANDLERS: Mapping[str, ToolHandler] = MappingProxyType(
    copy.deepcopy(
        {
            "synthorg_analytics_get_overview": _mk(
                "synthorg_analytics_get_overview",
                _WHY_ANALYTICS,
            ),
            "synthorg_analytics_get_trends": _mk(
                "synthorg_analytics_get_trends",
                _WHY_ANALYTICS,
            ),
            "synthorg_analytics_get_forecast": _mk(
                "synthorg_analytics_get_forecast",
                _WHY_ANALYTICS,
            ),
            "synthorg_metrics_get_current": _mk(
                "synthorg_metrics_get_current",
                _WHY_METRICS,
            ),
            "synthorg_metrics_get_history": _mk(
                "synthorg_metrics_get_history",
                _WHY_METRICS,
            ),
            "synthorg_reports_list": _mk("synthorg_reports_list", _WHY_REPORTS),
            "synthorg_reports_get": _mk("synthorg_reports_get", _WHY_REPORTS),
            "synthorg_reports_generate": _mk(
                "synthorg_reports_generate",
                _WHY_REPORTS,
            ),
        },
    ),
)
