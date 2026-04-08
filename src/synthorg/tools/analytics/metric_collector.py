"""Metric collector tool -- record custom metrics via a sink.

The ``MetricSink`` protocol defines a vendor-agnostic interface
for recording metrics.  No concrete implementation is shipped --
users inject a sink at construction time.
"""

import copy
from typing import Any, Final, Protocol, runtime_checkable

from synthorg.core.enums import ActionType
from synthorg.observability import get_logger
from synthorg.observability.events.analytics import (
    ANALYTICS_TOOL_METRIC_NOT_ALLOWED,
    ANALYTICS_TOOL_METRIC_RECORD_FAILED,
    ANALYTICS_TOOL_METRIC_RECORDED,
)
from synthorg.tools.analytics.base_analytics_tool import BaseAnalyticsTool
from synthorg.tools.analytics.config import AnalyticsToolsConfig  # noqa: TC001
from synthorg.tools.base import ToolExecutionResult

logger = get_logger(__name__)


@runtime_checkable
class MetricSink(Protocol):
    """Abstracted metric recording sink protocol.

    Implementations must be async and accept individual
    metric data points.
    """

    async def record(
        self,
        *,
        name: str,
        value: float,
        tags: dict[str, str] | None = None,
        unit: str | None = None,
    ) -> None:
        """Record a metric data point.

        Args:
            name: Metric name.
            value: Metric value.
            tags: Optional key-value tags for the data point.
            unit: Optional measurement unit.
        """
        ...


_PARAMETERS_SCHEMA: Final[dict[str, Any]] = {
    "type": "object",
    "properties": {
        "metric_name": {
            "type": "string",
            "description": "Name of the metric to record",
        },
        "value": {
            "type": "number",
            "description": "Metric value",
        },
        "tags": {
            "type": "object",
            "additionalProperties": {"type": "string"},
            "description": "Optional key-value tags",
        },
        "unit": {
            "type": "string",
            "description": "Optional measurement unit (e.g. 'seconds', 'bytes')",
        },
    },
    "required": ["metric_name", "value"],
    "additionalProperties": False,
}


class MetricCollectorTool(BaseAnalyticsTool):
    """Record custom metrics via an abstracted sink.

    Allows agents to record observations and measurements
    that are forwarded to the configured metric backend.

    Examples:
        Record a metric::

            tool = MetricCollectorTool(sink=my_sink)
            result = await tool.execute(
                arguments={
                    "metric_name": "response_time",
                    "value": 1.23,
                    "unit": "seconds",
                    "tags": {"endpoint": "/api/tasks"},
                }
            )
    """

    def __init__(
        self,
        *,
        sink: MetricSink | None = None,
        config: AnalyticsToolsConfig | None = None,
    ) -> None:
        """Initialize the metric collector tool.

        Args:
            sink: Metric recording sink.  ``None`` means the
                tool will return an error on execution.
            config: Analytics tool configuration.
        """
        super().__init__(
            name="metric_collector",
            description=(
                "Record custom metrics (counters, gauges, timings) "
                "to the configured metric backend."
            ),
            parameters_schema=copy.deepcopy(_PARAMETERS_SCHEMA),
            action_type=ActionType.CODE_READ,
            config=config,
        )
        self._sink = sink

    async def execute(
        self,
        *,
        arguments: dict[str, Any],
    ) -> ToolExecutionResult:
        """Record a metric data point.

        Args:
            arguments: Must contain ``metric_name`` and ``value``;
                optionally ``tags`` and ``unit``.

        Returns:
            A ``ToolExecutionResult`` confirming the recording.
        """
        if self._sink is None:
            logger.warning(
                ANALYTICS_TOOL_METRIC_RECORD_FAILED,
                metric_name=arguments.get("metric_name", "unknown"),
                error="sink_not_configured",
            )
            return ToolExecutionResult(
                content=(
                    "Metric recording requires a configured sink. "
                    "No MetricSink has been injected."
                ),
                is_error=True,
            )

        metric_name: str = arguments["metric_name"]
        value: float = arguments["value"]
        tags: dict[str, str] = arguments.get("tags") or {}
        unit: str | None = arguments.get("unit")

        if not self._is_metric_allowed(metric_name):
            logger.warning(
                ANALYTICS_TOOL_METRIC_NOT_ALLOWED,
                metric_name=metric_name,
            )
            return ToolExecutionResult(
                content=(
                    f"Metric not allowed: {metric_name!r}. "
                    f"Allowed: {sorted(self._config.allowed_metrics or set())}"
                ),
                is_error=True,
            )

        try:
            await self._sink.record(
                name=metric_name,
                value=value,
                tags=tags,
                unit=unit,
            )
        except MemoryError, RecursionError:
            raise
        except Exception as exc:
            logger.warning(
                ANALYTICS_TOOL_METRIC_RECORD_FAILED,
                metric_name=metric_name,
                error=str(exc),
            )
            return ToolExecutionResult(
                content=f"Metric recording failed: {exc}",
                is_error=True,
            )

        logger.info(
            ANALYTICS_TOOL_METRIC_RECORDED,
            metric_name=metric_name,
            value=value,
            unit=unit,
        )

        unit_suffix = f" {unit}" if unit else ""
        return ToolExecutionResult(
            content=(f"Metric recorded: {metric_name} = {value}{unit_suffix}"),
            metadata={
                "metric_name": metric_name,
                "value": value,
                "tags": tags,
                "unit": unit,
            },
        )
