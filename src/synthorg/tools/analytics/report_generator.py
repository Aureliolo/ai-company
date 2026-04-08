"""Report generator tool -- produce formatted analytics reports.

Delegates data fetching to an ``AnalyticsProvider`` and formats
the results into human-readable reports in text, markdown, or JSON.
"""

import copy
import json
from typing import Any, Final

from synthorg.core.enums import ActionType
from synthorg.observability import get_logger
from synthorg.observability.events.analytics import (
    ANALYTICS_TOOL_PROVIDER_NOT_CONFIGURED,
    ANALYTICS_TOOL_REPORT_FAILED,
    ANALYTICS_TOOL_REPORT_START,
    ANALYTICS_TOOL_REPORT_SUCCESS,
)
from synthorg.tools.analytics.base_analytics_tool import BaseAnalyticsTool
from synthorg.tools.analytics.config import AnalyticsToolsConfig  # noqa: TC001
from synthorg.tools.analytics.data_aggregator import (
    AnalyticsProvider,  # noqa: TC001
)
from synthorg.tools.base import ToolExecutionResult

logger = get_logger(__name__)

_REPORT_TYPES: Final[frozenset[str]] = frozenset(
    {
        "budget_summary",
        "performance",
        "trend_analysis",
        "cost_breakdown",
    }
)

_OUTPUT_FORMATS: Final[frozenset[str]] = frozenset({"text", "markdown", "json"})

_VALID_PERIODS: Final[frozenset[str]] = frozenset({"7d", "30d", "90d", "ytd", "custom"})

_REPORT_METRICS: Final[dict[str, list[str]]] = {
    "budget_summary": ["total_cost", "budget_remaining", "burn_rate"],
    "performance": [
        "task_completion_rate",
        "average_latency",
        "error_rate",
    ],
    "trend_analysis": ["total_cost", "task_count", "active_agents"],
    "cost_breakdown": [
        "cost_by_agent",
        "cost_by_department",
        "cost_by_model",
    ],
}

_PARAMETERS_SCHEMA: Final[dict[str, Any]] = {
    "type": "object",
    "properties": {
        "report_type": {
            "type": "string",
            "enum": sorted(_REPORT_TYPES),
            "description": "Type of report to generate",
        },
        "period": {
            "type": "string",
            "enum": sorted(_VALID_PERIODS),
            "description": "Reporting period",
        },
        "format": {
            "type": "string",
            "enum": sorted(_OUTPUT_FORMATS),
            "description": "Output format (default: markdown)",
            "default": "markdown",
        },
    },
    "required": ["report_type", "period"],
    "additionalProperties": False,
}


class ReportGeneratorTool(BaseAnalyticsTool):
    """Generate formatted analytics reports.

    Queries the analytics provider for relevant metrics and
    formats the results into a structured report.

    Examples:
        Generate a budget report::

            tool = ReportGeneratorTool(provider=my_provider)
            result = await tool.execute(
                arguments={
                    "report_type": "budget_summary",
                    "period": "30d",
                    "format": "markdown",
                }
            )
    """

    def __init__(
        self,
        *,
        provider: AnalyticsProvider | None = None,
        config: AnalyticsToolsConfig | None = None,
    ) -> None:
        """Initialize the report generator tool.

        Args:
            provider: Analytics data provider.  ``None`` means
                the tool will return an error on execution.
            config: Analytics tool configuration.
        """
        super().__init__(
            name="report_generator",
            description=(
                "Generate formatted analytics reports "
                "(budget, performance, trends, cost breakdown)."
            ),
            parameters_schema=copy.deepcopy(_PARAMETERS_SCHEMA),
            action_type=ActionType.CODE_READ,
            config=config,
        )
        self._provider = provider

    async def execute(
        self,
        *,
        arguments: dict[str, Any],
    ) -> ToolExecutionResult:
        """Generate an analytics report.

        Args:
            arguments: Must contain ``report_type`` and ``period``;
                optionally ``format``.

        Returns:
            A ``ToolExecutionResult`` with the formatted report.
        """
        if self._provider is None:
            logger.warning(
                ANALYTICS_TOOL_PROVIDER_NOT_CONFIGURED,
                tool="report_generator",
            )
            return ToolExecutionResult(
                content=(
                    "Report generation requires a configured provider. "
                    "No AnalyticsProvider has been injected."
                ),
                is_error=True,
            )

        report_type: str = arguments["report_type"]
        period: str = arguments["period"]
        output_format: str = arguments.get("format", "markdown")

        if report_type not in _REPORT_TYPES:
            return ToolExecutionResult(
                content=(
                    f"Invalid report_type: {report_type!r}. "
                    f"Must be one of: {sorted(_REPORT_TYPES)}"
                ),
                is_error=True,
            )

        if output_format not in _OUTPUT_FORMATS:
            return ToolExecutionResult(
                content=(
                    f"Invalid format: {output_format!r}. "
                    f"Must be one of: {sorted(_OUTPUT_FORMATS)}"
                ),
                is_error=True,
            )

        metrics = _REPORT_METRICS.get(report_type, [])

        logger.info(
            ANALYTICS_TOOL_REPORT_START,
            report_type=report_type,
            period=period,
            output_format=output_format,
        )

        try:
            data = await self._provider.query(
                metrics=metrics,
                period=period,
            )
        except MemoryError, RecursionError:
            raise
        except Exception as exc:
            logger.warning(
                ANALYTICS_TOOL_REPORT_FAILED,
                error=str(exc),
                report_type=report_type,
            )
            return ToolExecutionResult(
                content=f"Report generation failed: {exc}",
                is_error=True,
            )

        report = self._format_report(report_type, period, data, output_format)

        logger.info(
            ANALYTICS_TOOL_REPORT_SUCCESS,
            report_type=report_type,
            output_length=len(report),
        )

        return ToolExecutionResult(
            content=report,
            metadata={
                "report_type": report_type,
                "period": period,
                "format": output_format,
            },
        )

    @staticmethod
    def _format_report(
        report_type: str,
        period: str,
        data: dict[str, Any],
        output_format: str,
    ) -> str:
        """Format report data into the requested output format.

        Args:
            report_type: Type of report.
            period: Reporting period.
            data: Raw data from the analytics provider.
            output_format: Desired output format.

        Returns:
            Formatted report string.
        """
        if output_format == "json":
            return json.dumps(
                {
                    "report_type": report_type,
                    "period": period,
                    "data": data,
                },
                indent=2,
                default=str,
            )

        title = report_type.replace("_", " ").title()

        if output_format == "markdown":
            lines = [f"# {title} Report", "", f"**Period:** {period}", ""]
            for key, value in sorted(data.items()):
                lines.append(f"- **{key}:** {value}")
            return "\n".join(lines)

        # Plain text
        lines = [f"{title} Report", f"Period: {period}", ""]
        for key, value in sorted(data.items()):
            lines.append(f"  {key}: {value}")
        return "\n".join(lines)
