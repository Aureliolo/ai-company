"""Analytics controller -- derived read-only metrics."""

import asyncio
from collections import Counter
from datetime import UTC, datetime, timedelta
from typing import Annotated

from litestar import Controller, get
from litestar.datastructures import State  # noqa: TC002
from litestar.params import Parameter
from pydantic import BaseModel, ConfigDict, Field

from synthorg.api.dto import ApiResponse
from synthorg.api.errors import ServiceUnavailableError
from synthorg.api.guards import require_read_access
from synthorg.api.state import AppState  # noqa: TC001
from synthorg.budget.billing import billing_period_start
from synthorg.budget.trends import (
    BucketSize,
    ForecastPoint,
    TrendDataPoint,
    TrendMetric,
    TrendPeriod,
    bucket_cost_records,
    bucket_success_rate,
    bucket_task_completions,
    period_to_timedelta,
    project_daily_spend,
    resolve_bucket_size,
)
from synthorg.core.enums import TaskStatus
from synthorg.observability import get_logger
from synthorg.observability.events.analytics import (
    ANALYTICS_FORECAST_QUERIED,
    ANALYTICS_OVERVIEW_QUERIED,
    ANALYTICS_TRENDS_QUERIED,
)
from synthorg.observability.events.api import API_REQUEST_ERROR

logger = get_logger(__name__)


# ── Response models ────────────────────────────────────────────


class OverviewMetrics(BaseModel):
    """High-level analytics overview.

    Attributes:
        total_tasks: Total number of tasks.
        tasks_by_status: Task counts grouped by status.
        total_agents: Number of configured agents.
        total_cost_usd: Total cost across all records.
        budget_remaining_usd: Remaining budget for the current period.
        budget_used_percent: Percentage of monthly budget used.
        cost_7d_trend: Daily spend sparkline for the last 7 days.
        active_agents_count: Number of active agents.
        idle_agents_count: Number of non-active agents.
    """

    model_config = ConfigDict(frozen=True)

    total_tasks: int = Field(ge=0, description="Total number of tasks")
    tasks_by_status: dict[str, int] = Field(
        description="Task counts by status (keys are TaskStatus values)",
    )
    total_agents: int = Field(ge=0, description="Number of configured agents")
    total_cost_usd: float = Field(ge=0.0, description="Total cost in USD")
    budget_remaining_usd: float = Field(
        ge=0.0,
        description="Remaining budget for the current billing period",
    )
    budget_used_percent: float = Field(
        ge=0.0,
        description="Percentage of monthly budget used",
    )
    cost_7d_trend: tuple[TrendDataPoint, ...] = Field(
        description="Daily spend sparkline for the last 7 days",
    )
    active_agents_count: int = Field(ge=0, description="Number of active agents")
    idle_agents_count: int = Field(ge=0, description="Number of non-active agents")


class TrendsResponse(BaseModel):
    """Time-series trend data for a single metric.

    Attributes:
        period: Lookback period used.
        metric: Metric type queried.
        bucket_size: Time granularity of data points.
        data_points: Bucketed time-series data.
    """

    model_config = ConfigDict(frozen=True)

    period: str = Field(description="Lookback period (7d, 30d, 90d)")
    metric: str = Field(description="Metric type queried")
    bucket_size: str = Field(description="Bucket granularity (hour, day)")
    data_points: tuple[TrendDataPoint, ...] = Field(
        description="Bucketed time-series data points",
    )


class ForecastResponse(BaseModel):
    """Budget spend projection.

    Attributes:
        horizon_days: Projection horizon in days.
        projected_total_usd: Projected total additional spend.
        daily_projections: Per-day cumulative spend projections.
        days_until_exhausted: Days until budget exhaustion.
        confidence: Confidence score based on data density.
        avg_daily_spend_usd: Average daily spend used for projection.
    """

    model_config = ConfigDict(frozen=True)

    horizon_days: int = Field(ge=1, description="Projection horizon in days")
    projected_total_usd: float = Field(
        ge=0.0,
        description="Projected total additional spend",
    )
    daily_projections: tuple[ForecastPoint, ...] = Field(
        description="Per-day cumulative spend projections",
    )
    days_until_exhausted: int | None = Field(
        default=None,
        description="Days until budget exhaustion",
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence score based on data density",
    )
    avg_daily_spend_usd: float = Field(
        ge=0.0,
        description="Average daily spend used for projection",
    )


# ── Controller ─────────────────────────────────────────────────


class AnalyticsController(Controller):
    """Derived analytics and metrics."""

    path = "/analytics"
    tags = ("analytics",)

    @get("/overview", guards=[require_read_access])
    async def get_overview(
        self,
        state: State,
    ) -> ApiResponse[OverviewMetrics]:
        """Return high-level metrics overview.

        Includes task counts, cost totals, budget status, 7-day spend
        sparkline, and agent activity counts.

        Args:
            state: Application state.

        Returns:
            Overview metrics envelope.
        """
        app_state: AppState = state.app_state
        now = datetime.now(UTC)

        try:
            async with asyncio.TaskGroup() as tg:
                t_tasks = tg.create_task(app_state.persistence.tasks.list_tasks())
                t_cost = tg.create_task(app_state.cost_tracker.get_total_cost())
                t_agents = tg.create_task(app_state.config_resolver.get_agents())
                t_7d_records = tg.create_task(
                    app_state.cost_tracker.get_records(
                        start=now - timedelta(days=7),
                    ),
                )
        except ExceptionGroup as eg:
            logger.warning(
                API_REQUEST_ERROR,
                endpoint="analytics.overview",
                error_count=len(eg.exceptions),
                exc_info=True,
            )
            raise eg.exceptions[0] from eg

        all_tasks = t_tasks.result()
        total_cost = t_cost.result()
        agents = t_agents.result()
        records_7d = t_7d_records.result()

        # Task status breakdown
        counts = Counter(t.status.value for t in all_tasks)
        by_status = {s.value: counts.get(s.value, 0) for s in TaskStatus}

        # Budget context
        budget_config = app_state.cost_tracker.budget_config
        budget_monthly = budget_config.total_monthly if budget_config else 0.0
        if budget_monthly > 0 and budget_config is not None:
            period_start = billing_period_start(budget_config.reset_day)
            try:
                period_cost = await app_state.cost_tracker.get_total_cost(
                    start=period_start,
                )
            except MemoryError, RecursionError:
                raise
            except Exception:
                period_cost = total_cost
            budget_used_pct = round(period_cost / budget_monthly * 100, 2)
            budget_remaining = max(budget_monthly - period_cost, 0.0)
        else:
            budget_used_pct = 0.0
            budget_remaining = 0.0

        # 7-day cost sparkline
        cost_7d_trend = bucket_cost_records(
            records_7d,
            now - timedelta(days=7),
            now,
            BucketSize.DAY,
        )

        # Agent counts
        active_count, idle_count = await _resolve_agent_counts(
            app_state,
            len(agents),
        )

        logger.debug(
            ANALYTICS_OVERVIEW_QUERIED,
            total_tasks=len(all_tasks),
            total_cost_usd=total_cost,
            active_agents=active_count,
        )

        return ApiResponse(
            data=OverviewMetrics(
                total_tasks=len(all_tasks),
                tasks_by_status=by_status,
                total_agents=len(agents),
                total_cost_usd=total_cost,
                budget_remaining_usd=budget_remaining,
                budget_used_percent=budget_used_pct,
                cost_7d_trend=cost_7d_trend,
                active_agents_count=active_count,
                idle_agents_count=idle_count,
            ),
        )

    @get("/trends", guards=[require_read_access])
    async def get_trends(
        self,
        state: State,
        period: Annotated[
            TrendPeriod,
            Parameter(description="Lookback period"),
        ] = TrendPeriod.SEVEN_DAYS,
        metric: Annotated[
            TrendMetric,
            Parameter(description="Metric to trend"),
        ] = TrendMetric.SPEND,
    ) -> ApiResponse[TrendsResponse]:
        """Return time-series trend data for a metric.

        Args:
            state: Application state.
            period: Lookback period (7d, 30d, 90d).
            metric: Metric type to trend.

        Returns:
            Bucketed trend data envelope.
        """
        app_state: AppState = state.app_state
        now = datetime.now(UTC)
        start = now - period_to_timedelta(period)
        bucket_size = resolve_bucket_size(period)

        data_points: tuple[TrendDataPoint, ...]

        if metric == TrendMetric.SPEND:
            records = await app_state.cost_tracker.get_records(start=start)
            data_points = bucket_cost_records(records, start, now, bucket_size)

        elif metric in (TrendMetric.TASKS_COMPLETED, TrendMetric.SUCCESS_RATE):
            try:
                task_metrics = app_state.performance_tracker.get_task_metrics(
                    since=start,
                )
            except ServiceUnavailableError:
                data_points = ()
            else:
                if metric == TrendMetric.TASKS_COMPLETED:
                    data_points = bucket_task_completions(
                        task_metrics,
                        start,
                        now,
                        bucket_size,
                    )
                else:
                    data_points = bucket_success_rate(
                        task_metrics,
                        start,
                        now,
                        bucket_size,
                    )

        else:
            # ACTIVE_AGENTS: flat line at current count (no historical snapshots)
            active_count, _ = await _resolve_agent_counts(app_state, 0)
            data_points = tuple(
                TrendDataPoint(timestamp=bucket_start, value=float(active_count))
                for bucket_start in _generate_bucket_starts(start, now, bucket_size)
            )

        logger.debug(
            ANALYTICS_TRENDS_QUERIED,
            period=period.value,
            metric=metric.value,
            bucket_size=bucket_size.value,
            data_point_count=len(data_points),
        )

        return ApiResponse(
            data=TrendsResponse(
                period=period.value,
                metric=metric.value,
                bucket_size=bucket_size.value,
                data_points=data_points,
            ),
        )

    @get("/forecast", guards=[require_read_access])
    async def get_forecast(
        self,
        state: State,
        horizon_days: Annotated[
            int,
            Parameter(ge=1, le=90, description="Projection horizon in days"),
        ] = 14,
    ) -> ApiResponse[ForecastResponse]:
        """Return budget spend projection.

        Uses average daily spend over the lookback period
        (equal to horizon_days) to project future spend.

        Args:
            state: Application state.
            horizon_days: Number of days to project forward.

        Returns:
            Forecast data envelope.
        """
        app_state: AppState = state.app_state
        now = datetime.now(UTC)
        lookback_start = now - timedelta(days=horizon_days)

        records = await app_state.cost_tracker.get_records(start=lookback_start)

        # Budget context for exhaustion calculation
        budget_config = app_state.cost_tracker.budget_config
        budget_monthly = budget_config.total_monthly if budget_config else 0.0
        budget_remaining = 0.0
        if budget_monthly > 0 and budget_config is not None:
            period_start = billing_period_start(budget_config.reset_day)
            try:
                period_cost = await app_state.cost_tracker.get_total_cost(
                    start=period_start,
                )
            except MemoryError, RecursionError:
                raise
            except Exception:
                period_cost = 0.0
            budget_remaining = max(budget_monthly - period_cost, 0.0)

        forecast = project_daily_spend(
            records,
            horizon_days=horizon_days,
            budget_total_monthly=budget_monthly,
            budget_remaining_usd=budget_remaining,
        )

        logger.debug(
            ANALYTICS_FORECAST_QUERIED,
            horizon_days=horizon_days,
            projected_total_usd=forecast.projected_total_usd,
            days_until_exhausted=forecast.days_until_exhausted,
        )

        return ApiResponse(
            data=ForecastResponse(
                horizon_days=horizon_days,
                projected_total_usd=forecast.projected_total_usd,
                daily_projections=forecast.daily_projections,
                days_until_exhausted=forecast.days_until_exhausted,
                confidence=forecast.confidence,
                avg_daily_spend_usd=forecast.avg_daily_spend_usd,
            ),
        )


# ── Helpers ────────────────────────────────────────────────────


async def _resolve_agent_counts(
    app_state: AppState,
    config_agent_count: int,
) -> tuple[int, int]:
    """Resolve active and idle agent counts.

    Uses AgentRegistryService when available, falls back to
    config_resolver count (all active, zero idle).

    Args:
        app_state: Application state.
        config_agent_count: Fallback total from config.

    Returns:
        Tuple of (active_count, idle_count).
    """
    if app_state.has_agent_registry:
        try:
            active = await app_state.agent_registry.list_active()
            total = await app_state.agent_registry.agent_count()
            return len(active), total - len(active)
        except MemoryError, RecursionError:
            raise
        except Exception:
            logger.warning(
                API_REQUEST_ERROR,
                endpoint="analytics.resolve_agent_counts",
                error="agent_registry_query_failed",
            )
    return config_agent_count, 0


def _generate_bucket_starts(
    start: datetime,
    end: datetime,
    bucket_size: BucketSize,
) -> list[datetime]:
    """Generate bucket start times for active_agents flat line.

    Delegates to the trends module's internal logic via
    a minimal reimplementation to avoid importing private helpers.

    Args:
        start: Period start.
        end: Period end.
        bucket_size: Granularity.

    Returns:
        List of bucket start datetimes.
    """
    step = timedelta(hours=1) if bucket_size == BucketSize.HOUR else timedelta(days=1)
    current = start.replace(minute=0, second=0, microsecond=0)
    if bucket_size == BucketSize.DAY:
        current = current.replace(hour=0)
    buckets: list[datetime] = []
    while current < end:
        buckets.append(current)
        current = current + step
    return buckets
