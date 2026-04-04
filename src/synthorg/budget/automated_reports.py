"""Automated report generation service.

Composes existing trackers (cost, risk, performance) and the
CFO ``ReportGenerator`` to produce periodic comprehensive reports.

Service layer for the Automated Reporting section of the Operations
design page.
"""

import math
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from synthorg.budget.report_config import ReportPeriod
from synthorg.budget.report_templates import (
    AgentPerformanceSummary,
    ComprehensiveReport,
    DailyRiskPoint,
    PerformanceMetricsReport,
    RiskTrendsReport,
    TaskCompletionReport,
)
from synthorg.observability import get_logger
from synthorg.observability.events.reporting import (
    REPORTING_GENERATION_COMPLETED,
    REPORTING_GENERATION_FAILED,
    REPORTING_GENERATION_STARTED,
    REPORTING_PERIOD_COMPUTED,
    REPORTING_SERVICE_CREATED,
)

if TYPE_CHECKING:
    from synthorg.budget.report_config import AutomatedReportingConfig
    from synthorg.budget.reports import ReportGenerator, SpendingReport
    from synthorg.budget.risk_record import RiskRecord
    from synthorg.budget.risk_tracker import RiskTracker
    from synthorg.budget.tracker import CostTracker
    from synthorg.hr.performance.tracker import PerformanceTracker

logger = get_logger(__name__)


class AutomatedReportService:
    """Generates comprehensive periodic reports.

    Composes existing services to produce reports covering spending,
    performance, task completion, and risk trends.

    Args:
        report_generator: CFO spending report generator.
        cost_tracker: Cost tracking service.
        risk_tracker: Optional risk tracking service.
        performance_tracker: Optional performance tracking service.
        config: Optional automated reporting configuration.
    """

    def __init__(
        self,
        *,
        report_generator: ReportGenerator,
        cost_tracker: CostTracker,
        risk_tracker: RiskTracker | None = None,
        performance_tracker: PerformanceTracker | None = None,
        config: AutomatedReportingConfig | None = None,
    ) -> None:
        self._report_generator = report_generator
        self._cost_tracker = cost_tracker
        self._risk_tracker = risk_tracker
        self._performance_tracker = performance_tracker
        self._config = config
        logger.debug(
            REPORTING_SERVICE_CREATED,
            has_risk_tracker=risk_tracker is not None,
            has_performance_tracker=performance_tracker is not None,
        )

    async def generate_spending_report(
        self,
        *,
        start: datetime,
        end: datetime,
        top_n: int = 10,
    ) -> SpendingReport:
        """Generate a spending report for the given period.

        Delegates to the existing ``ReportGenerator``.
        """
        return await self._report_generator.generate_report(
            start=start,
            end=end,
            top_n=top_n,
        )

    async def generate_performance_report(
        self,
        *,
        start: datetime,
        end: datetime,
    ) -> PerformanceMetricsReport:
        """Generate a performance metrics report.

        Queries ``PerformanceTracker`` for task metrics in the period.
        Returns an empty report when no performance tracker is available.
        """
        now = datetime.now(UTC)

        if self._performance_tracker is None:
            return PerformanceMetricsReport(generated_at=now)

        task_metrics = self._performance_tracker.get_task_metrics(
            since=start,
            until=end,
        )

        # Group by agent.
        by_agent: dict[str, list[object]] = defaultdict(list)
        for metric in task_metrics:
            by_agent[metric.agent_id].append(metric)

        snapshots: list[AgentPerformanceSummary] = []
        all_quality_scores: list[float] = []

        for agent_id in sorted(by_agent):
            agent_metrics = by_agent[agent_id]
            completed = sum(1 for m in agent_metrics if getattr(m, "success", False))
            failed = len(agent_metrics) - completed
            quality_scores = [getattr(m, "quality_score", None) for m in agent_metrics]
            valid_scores = [s for s in quality_scores if s is not None]
            avg_quality = (
                round(math.fsum(valid_scores) / len(valid_scores), 2)
                if valid_scores
                else None
            )
            if avg_quality is not None:
                all_quality_scores.append(avg_quality)

            # Get cost from cost tracker.
            agent_cost = await self._cost_tracker.get_agent_cost(
                agent_id,
                start=start,
                end=end,
            )

            # Get risk from risk tracker.
            agent_risk = 0.0
            if self._risk_tracker is not None:
                agent_risk = await self._risk_tracker.get_agent_risk(
                    agent_id,
                    start=start,
                    end=end,
                )

            snapshots.append(
                AgentPerformanceSummary(
                    agent_id=agent_id,
                    tasks_completed=completed,
                    tasks_failed=failed,
                    average_quality_score=avg_quality,
                    total_cost_usd=agent_cost,
                    total_risk_units=agent_risk,
                ),
            )

        org_avg = (
            round(math.fsum(all_quality_scores) / len(all_quality_scores), 2)
            if all_quality_scores
            else None
        )
        total_completed = sum(s.tasks_completed for s in snapshots)
        total_failed = sum(s.tasks_failed for s in snapshots)

        return PerformanceMetricsReport(
            agent_snapshots=tuple(snapshots),
            average_quality_score=org_avg,
            total_tasks_completed=total_completed,
            total_tasks_failed=total_failed,
            generated_at=now,
        )

    async def generate_task_completion_report(
        self,
        *,
        start: datetime,
        end: datetime,
    ) -> TaskCompletionReport:
        """Generate a task completion report.

        Derives task counts from cost records (each unique task_id
        represents an assigned task).
        """
        now = datetime.now(UTC)
        records = await self._cost_tracker.get_records(
            start=start,
            end=end,
        )
        task_ids = {r.task_id for r in records}
        total_assigned = len(task_ids)

        return TaskCompletionReport(
            total_assigned=total_assigned,
            total_completed=total_assigned,
            generated_at=now,
        )

    async def generate_risk_trends_report(
        self,
        *,
        start: datetime,
        end: datetime,
    ) -> RiskTrendsReport:
        """Generate a risk trends report.

        Returns an empty report when no risk tracker is available.
        """
        now = datetime.now(UTC)

        if self._risk_tracker is None:
            return RiskTrendsReport(generated_at=now)

        records = await self._risk_tracker.get_records(
            start=start,
            end=end,
        )
        total_risk = math.fsum(r.risk_units for r in records)

        # Per-agent aggregation.
        by_agent: dict[str, float] = defaultdict(float)
        for r in records:
            by_agent[r.agent_id] += r.risk_units
        risk_by_agent = tuple(
            sorted(by_agent.items(), key=lambda x: x[1], reverse=True),
        )

        # Per-action-type aggregation.
        by_action: dict[str, float] = defaultdict(float)
        for r in records:
            by_action[r.action_type] += r.risk_units
        risk_by_action_type = tuple(
            sorted(by_action.items(), key=lambda x: x[1], reverse=True),
        )

        # Daily trend.
        daily: dict[str, list[RiskRecord]] = defaultdict(list)
        for r in records:
            day_key = r.timestamp.date().isoformat()
            daily[day_key].append(r)
        daily_trend = tuple(
            DailyRiskPoint(
                date=datetime.fromisoformat(day_key).date(),
                total_risk_units=math.fsum(rec.risk_units for rec in day_records),
                record_count=len(day_records),
            )
            for day_key, day_records in sorted(daily.items())
        )

        return RiskTrendsReport(
            total_risk_units=total_risk,
            risk_by_agent=risk_by_agent,
            risk_by_action_type=risk_by_action_type,
            daily_risk_trend=daily_trend,
            generated_at=now,
        )

    async def generate_comprehensive_report(
        self,
        *,
        period: ReportPeriod,
        reference_time: datetime | None = None,
    ) -> ComprehensiveReport:
        """Generate a comprehensive report for the given period.

        Composes all sub-reports (spending, performance, task completion,
        risk trends) into a single report.

        Args:
            period: The report period (daily/weekly/monthly).
            reference_time: Reference time for period computation.
                Defaults to current UTC time.

        Returns:
            Comprehensive report with all available sub-reports.
        """
        ref = reference_time or datetime.now(UTC)
        start, end = compute_period_range(period, ref)
        now = datetime.now(UTC)

        logger.info(
            REPORTING_GENERATION_STARTED,
            period=period.value,
            start=start.isoformat(),
            end=end.isoformat(),
        )

        try:
            spending = await self.generate_spending_report(
                start=start,
                end=end,
            )
            performance = await self.generate_performance_report(
                start=start,
                end=end,
            )
            task_completion = await self.generate_task_completion_report(
                start=start,
                end=end,
            )
            risk_trends = await self.generate_risk_trends_report(
                start=start,
                end=end,
            )
        except MemoryError, RecursionError:
            raise
        except Exception:
            logger.exception(
                REPORTING_GENERATION_FAILED,
                period=period.value,
            )
            raise

        report = ComprehensiveReport(
            period=period,
            start=start,
            end=end,
            spending=spending,
            performance=performance,
            task_completion=task_completion,
            risk_trends=risk_trends,
            generated_at=now,
        )

        logger.info(
            REPORTING_GENERATION_COMPLETED,
            period=period.value,
            has_spending=spending is not None,
            has_performance=performance is not None,
            has_risk_trends=risk_trends is not None,
        )

        return report


def compute_period_range(
    period: ReportPeriod,
    reference: datetime,
) -> tuple[datetime, datetime]:
    """Compute the start and end times for a report period.

    Args:
        period: The report period.
        reference: Reference time.

    Returns:
        (start, end) tuple where start is inclusive and end is exclusive.
    """
    if period == ReportPeriod.DAILY:
        # Previous day: 00:00 UTC to 00:00 UTC.
        today = reference.replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
            tzinfo=UTC,
        )
        start = today - timedelta(days=1)
        end = today
    elif period == ReportPeriod.WEEKLY:
        # Previous week: Monday 00:00 UTC to Monday 00:00 UTC.
        today = reference.replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
            tzinfo=UTC,
        )
        # Monday of current week.
        current_monday = today - timedelta(days=today.weekday())
        start = current_monday - timedelta(weeks=1)
        end = current_monday
    else:
        # Previous month: 1st to 1st.
        first_of_month = reference.replace(
            day=1,
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
            tzinfo=UTC,
        )
        end = first_of_month
        # First of previous month.
        if first_of_month.month == 1:
            start = first_of_month.replace(
                year=first_of_month.year - 1,
                month=12,
            )
        else:
            start = first_of_month.replace(month=first_of_month.month - 1)

    logger.debug(
        REPORTING_PERIOD_COMPUTED,
        period=period.value,
        start=start.isoformat(),
        end=end.isoformat(),
    )
    return start, end
