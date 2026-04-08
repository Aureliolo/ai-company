"""Real-time cost tracking service.

Provides an in-memory store with TTL-based eviction for
:class:`CostRecord` entries and aggregation queries consumed by the CFO
agent and budget monitoring.

Service layer for the cost tracking schema defined in the Operations
design page.  The current implementation is purely in-memory;
persistence integration is planned.
"""

import asyncio
import math
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, NamedTuple

from synthorg.budget.call_category import OrchestrationAlertLevel
from synthorg.budget.category_analytics import (
    CategoryBreakdown,
    OrchestrationRatio,
    build_category_breakdown,
    compute_orchestration_ratio,
)
from synthorg.budget.enums import BudgetAlertLevel
from synthorg.budget.spending_summary import (
    AgentSpending,
    DepartmentSpending,
    PeriodSpending,
    SpendingSummary,
)
from synthorg.constants import BUDGET_ROUNDING_PRECISION
from synthorg.observability import get_logger
from synthorg.observability.events.budget import (
    BUDGET_AGENT_COST_QUERIED,
    BUDGET_CATEGORY_BREAKDOWN_QUERIED,
    BUDGET_DEPARTMENT_RESOLVE_FAILED,
    BUDGET_ORCHESTRATION_RATIO_ALERT,
    BUDGET_ORCHESTRATION_RATIO_QUERIED,
    BUDGET_PROJECT_COST_AGGREGATED,
    BUDGET_PROJECT_COST_AGGREGATION_FAILED,
    BUDGET_PROJECT_COST_QUERIED,
    BUDGET_PROJECT_RECORDS_QUERIED,
    BUDGET_PROVIDER_USAGE_QUERIED,
    BUDGET_QUERY_EXCEEDS_RETENTION,
    BUDGET_RECORD_ADDED,
    BUDGET_RECORDS_AUTO_PRUNED,
    BUDGET_RECORDS_PRUNED,
    BUDGET_RECORDS_QUERIED,
    BUDGET_SUMMARY_BUILT,
    BUDGET_TIME_RANGE_INVALID,
    BUDGET_TOTAL_COST_QUERIED,
    BUDGET_TRACKER_CREATED,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from synthorg.budget.config import BudgetConfig
    from synthorg.budget.coordination_config import (
        OrchestrationAlertThresholds,
    )
    from synthorg.budget.cost_record import CostRecord
    from synthorg.budget.project_cost_aggregate import (
        ProjectCostAggregateRepository,
    )

from synthorg.core.types import NotBlankStr  # noqa: TC001

logger = get_logger(__name__)

_COST_WINDOW_HOURS = 168  # 7 days
_AUTO_PRUNE_THRESHOLD = 100_000


class ProviderUsageSummary(NamedTuple):
    """Per-provider usage totals for a time window."""

    total_tokens: int
    total_cost: float


class _AggregateResult(NamedTuple):
    """Aggregated cost and token totals."""

    cost: float
    input_tokens: int
    output_tokens: int
    record_count: int


class CostTracker:
    """In-memory cost tracking service with TTL-based eviction.

    Records :class:`CostRecord` entries from LLM API calls and provides
    aggregation queries for budget monitoring.  Memory is bounded by a
    soft TTL-based auto-prune: when the record count exceeds
    *auto_prune_threshold*, records older than 168 hours (7 days)
    are removed on the next query.

    Args:
        budget_config: Optional budget configuration for alert level
            computation.  When ``None``, alert level defaults to
            ``NORMAL`` and ``budget_used_percent`` to ``0.0``.
        department_resolver: Optional callable mapping ``agent_id`` to a
            department name.  When ``None`` or returning ``None`` for an
            agent, the agent is excluded from department aggregation.
        auto_prune_threshold: Maximum record count before auto-pruning
            is triggered on snapshot.  Defaults to 100,000.

    Raises:
        ValueError: If *auto_prune_threshold* < 1.
    """

    def __init__(
        self,
        *,
        budget_config: BudgetConfig | None = None,
        department_resolver: Callable[[str], str | None] | None = None,
        auto_prune_threshold: int = _AUTO_PRUNE_THRESHOLD,
        project_cost_repo: ProjectCostAggregateRepository | None = None,
    ) -> None:
        if auto_prune_threshold < 1:
            msg = f"auto_prune_threshold must be >= 1, got {auto_prune_threshold}"
            raise ValueError(msg)
        self._records: list[CostRecord] = []
        self._lock: asyncio.Lock = asyncio.Lock()
        self._budget_config = budget_config
        self._department_resolver = department_resolver
        self._auto_prune_threshold = auto_prune_threshold
        self._project_cost_repo = project_cost_repo
        logger.debug(
            BUDGET_TRACKER_CREATED,
            has_budget_config=budget_config is not None,
            has_department_resolver=department_resolver is not None,
            has_project_cost_repo=project_cost_repo is not None,
        )

    @property
    def budget_config(self) -> BudgetConfig | None:
        """The optional budget configuration.

        Returns:
            Budget config if set, else ``None``.
        """
        return self._budget_config

    async def record(self, cost_record: CostRecord) -> None:
        """Append a cost record.

        The in-memory append runs under ``_lock``.  After the lock
        is released, ``_update_project_aggregate`` is awaited to
        update the durable project cost aggregate when the record
        has a ``project_id`` and a repository is configured.
        Aggregate updates are best-effort: failures are logged at
        WARNING but do not affect the in-memory recording.

        Args:
            cost_record: Immutable cost record to store.
        """
        # Lock protects in-memory list only.  DB aggregate update is
        # best-effort and runs outside the lock to avoid blocking other
        # callers on I/O.
        async with self._lock:
            self._records.append(cost_record)
            logger.info(
                BUDGET_RECORD_ADDED,
                agent_id=cost_record.agent_id,
                model=cost_record.model,
                cost_usd=cost_record.cost_usd,
            )

        await self._update_project_aggregate(cost_record)

    async def prune_expired(self, *, now: datetime | None = None) -> int:
        """Remove records older than the 168-hour (7-day) cost window.

        Call periodically from long-running services to bound
        memory growth.

        Args:
            now: Reference time.  Defaults to current UTC time.

        Returns:
            Number of records removed.
        """
        ref = now or datetime.now(UTC)
        cutoff = ref - timedelta(hours=_COST_WINDOW_HOURS)
        async with self._lock:
            pruned = self._prune_before(cutoff)
            if pruned:
                logger.info(
                    BUDGET_RECORDS_PRUNED,
                    pruned=pruned,
                    remaining=len(self._records),
                )
            return pruned

    async def get_total_cost(
        self,
        *,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> float:
        """Sum of ``cost_usd`` across all records, optionally filtered by time.

        Args:
            start: Inclusive lower bound on ``timestamp``.
            end: Exclusive upper bound on ``timestamp``.

        Returns:
            Rounded total cost in USD (base currency).

        Raises:
            ValueError: If both *start* and *end* are given and
                ``start >= end``.
        """
        _validate_time_range(start, end)
        logger.debug(BUDGET_TOTAL_COST_QUERIED, start=start, end=end)
        snapshot = await self._snapshot()
        filtered = _filter_records(snapshot, start=start, end=end)
        return _aggregate(filtered).cost

    async def get_agent_cost(
        self,
        agent_id: str,
        *,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> float:
        """Sum of ``cost_usd`` for a single agent, optionally filtered by time.

        Args:
            agent_id: Agent identifier to filter by.
            start: Inclusive lower bound on ``timestamp``.
            end: Exclusive upper bound on ``timestamp``.

        Returns:
            Rounded total cost in USD (base currency) for the agent.

        Raises:
            ValueError: If both *start* and *end* are given and
                ``start >= end``.
        """
        _validate_time_range(start, end)
        logger.debug(
            BUDGET_AGENT_COST_QUERIED,
            agent_id=agent_id,
            start=start,
            end=end,
        )
        snapshot = await self._snapshot()
        filtered = _filter_records(
            snapshot,
            agent_id=agent_id,
            start=start,
            end=end,
        )
        return _aggregate(filtered).cost

    async def get_project_cost(
        self,
        project_id: NotBlankStr,
        *,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> float:
        """Sum of ``cost_usd`` for a single project.

        Args:
            project_id: Project identifier to filter by.
            start: Inclusive lower bound on ``timestamp``.
            end: Exclusive upper bound on ``timestamp``.

        Returns:
            Rounded total cost in USD (base currency) for the project.

        Raises:
            ValueError: If both *start* and *end* are given and
                ``start >= end``.
        """
        _validate_time_range(start, end)
        logger.debug(
            BUDGET_PROJECT_COST_QUERIED,
            project_id=project_id,
            start=start,
            end=end,
        )
        snapshot = await self._snapshot()
        filtered = _filter_records(
            snapshot,
            project_id=project_id,
            start=start,
            end=end,
        )
        return _aggregate(filtered).cost

    async def get_project_records(
        self,
        project_id: NotBlankStr,
        *,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> tuple[CostRecord, ...]:
        """Return cost records for a specific project.

        Args:
            project_id: Project identifier to filter by.
            start: Inclusive lower bound on ``timestamp``.
            end: Exclusive upper bound on ``timestamp``.

        Returns:
            Immutable tuple of matching cost records.

        Raises:
            ValueError: If both *start* and *end* are given and
                ``start >= end``.
        """
        _validate_time_range(start, end)
        logger.debug(
            BUDGET_PROJECT_RECORDS_QUERIED,
            project_id=project_id,
            start=start,
            end=end,
        )
        snapshot = await self._snapshot()
        return _filter_records(
            snapshot,
            project_id=project_id,
            start=start,
            end=end,
        )

    async def get_record_count(self) -> int:
        """Total number of recorded cost entries.

        Returns:
            Number of cost records.
        """
        async with self._lock:
            return len(self._records)

    async def get_records(
        self,
        *,
        agent_id: str | None = None,
        task_id: str | None = None,
        provider: NotBlankStr | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> tuple[CostRecord, ...]:
        """Return filtered cost records.

        Returns an immutable snapshot of records matching the filters.

        Args:
            agent_id: Filter by agent.
            task_id: Filter by task.
            provider: Filter by provider name.
            start: Inclusive lower bound on ``timestamp``.
            end: Exclusive upper bound on ``timestamp``.

        Returns:
            Immutable tuple of matching cost records.

        Raises:
            ValueError: If both *start* and *end* are given and
                ``start >= end``.
        """
        _validate_time_range(start, end)
        logger.debug(
            BUDGET_RECORDS_QUERIED,
            agent_id=agent_id,
            task_id=task_id,
            provider=provider,
            start=start,
            end=end,
        )
        snapshot = await self._snapshot()
        return _filter_records(
            snapshot,
            agent_id=agent_id,
            task_id=task_id,
            provider=provider,
            start=start,
            end=end,
        )

    async def get_provider_usage(
        self,
        provider_name: NotBlankStr,
        *,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> ProviderUsageSummary:
        """Return aggregated token and cost totals for a provider.

        Args:
            provider_name: Provider to aggregate usage for.
            start: Inclusive lower bound on ``timestamp``.
            end: Exclusive upper bound on ``timestamp``.

        Returns:
            Total tokens (input + output) and total cost.

        Raises:
            ValueError: If both *start* and *end* are given and
                ``start >= end``.
        """
        _validate_time_range(start, end)
        logger.debug(
            BUDGET_PROVIDER_USAGE_QUERIED,
            provider=provider_name,
            start=start,
            end=end,
        )
        snapshot = await self._snapshot()
        filtered = _filter_records(
            snapshot,
            provider=provider_name,
            start=start,
            end=end,
        )
        if not filtered:
            return ProviderUsageSummary(total_tokens=0, total_cost=0.0)
        agg = _aggregate(filtered)
        return ProviderUsageSummary(
            total_tokens=agg.input_tokens + agg.output_tokens,
            total_cost=agg.cost,
        )

    async def build_summary(
        self,
        *,
        start: datetime,
        end: datetime,
    ) -> SpendingSummary:
        """Build a spending summary for the given period.

        Args:
            start: Inclusive period start.
            end: Exclusive period end.

        Returns:
            Aggregated spending summary with breakdowns and alert level.

        Raises:
            ValueError: If ``start >= end``.
        """
        _validate_time_range(start, end)
        retention_cutoff = datetime.now(UTC) - timedelta(
            hours=_COST_WINDOW_HOURS,
        )
        if start < retention_cutoff:
            logger.warning(
                BUDGET_QUERY_EXCEEDS_RETENTION,
                requested_start=start.isoformat(),
                retention_cutoff=retention_cutoff.isoformat(),
                retention_hours=_COST_WINDOW_HOURS,
            )
        snapshot = await self._snapshot()
        filtered = _filter_records(snapshot, start=start, end=end)
        totals = _aggregate(filtered)

        agent_spendings = _build_agent_spendings(filtered)
        dept_spendings = self._build_dept_spendings(agent_spendings)
        budget_monthly, used_pct, alert = self._build_budget_context(
            totals.cost,
        )

        summary = SpendingSummary(
            period=PeriodSpending(
                start=start,
                end=end,
                total_cost_usd=totals.cost,
                total_input_tokens=totals.input_tokens,
                total_output_tokens=totals.output_tokens,
                record_count=totals.record_count,
            ),
            by_agent=tuple(agent_spendings),
            by_department=tuple(dept_spendings),
            budget_total_monthly=budget_monthly,
            budget_used_percent=used_pct,
            alert_level=alert,
        )

        logger.info(
            BUDGET_SUMMARY_BUILT,
            total_cost_usd=totals.cost,
            record_count=totals.record_count,
            agent_count=len(agent_spendings),
            department_count=len(dept_spendings),
            alert_level=alert.value,
        )

        return summary

    async def get_category_breakdown(
        self,
        *,
        agent_id: str | None = None,
        task_id: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> CategoryBreakdown:
        """Build a per-category cost breakdown.

        Args:
            agent_id: Filter by agent.
            task_id: Filter by task.
            start: Inclusive lower bound on timestamp.
            end: Exclusive upper bound on timestamp.

        Returns:
            Category breakdown of cost, tokens, and call counts.

        Raises:
            ValueError: If ``start >= end``.
        """
        _validate_time_range(start, end)
        logger.debug(
            BUDGET_CATEGORY_BREAKDOWN_QUERIED,
            agent_id=agent_id,
            task_id=task_id,
            start=start,
            end=end,
        )
        snapshot = await self._snapshot()
        filtered = _filter_records(
            snapshot,
            agent_id=agent_id,
            task_id=task_id,
            start=start,
            end=end,
        )
        return build_category_breakdown(filtered)

    async def get_orchestration_ratio(
        self,
        *,
        agent_id: str | None = None,
        task_id: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
        thresholds: OrchestrationAlertThresholds | None = None,
    ) -> OrchestrationRatio:
        """Compute the orchestration overhead ratio.

        Args:
            agent_id: Filter by agent.
            task_id: Filter by task.
            start: Inclusive lower bound on timestamp.
            end: Exclusive upper bound on timestamp.
            thresholds: Optional custom alert thresholds.

        Returns:
            Orchestration ratio with alert level.

        Raises:
            ValueError: If ``start >= end``.
        """
        breakdown = await self.get_category_breakdown(
            agent_id=agent_id,
            task_id=task_id,
            start=start,
            end=end,
        )
        result = compute_orchestration_ratio(
            breakdown,
            thresholds=thresholds,
        )
        logger.debug(
            BUDGET_ORCHESTRATION_RATIO_QUERIED,
            agent_id=agent_id,
            task_id=task_id,
            ratio=result.ratio,
            alert_level=result.alert_level.value,
        )
        if result.alert_level != OrchestrationAlertLevel.NORMAL:
            logger.warning(
                BUDGET_ORCHESTRATION_RATIO_ALERT,
                agent_id=agent_id,
                task_id=task_id,
                ratio=result.ratio,
                alert_level=result.alert_level.value,
            )
        return result

    # ── Private helpers ──────────────────────────────────────────────

    async def _update_project_aggregate(
        self,
        cost_record: CostRecord,
    ) -> None:
        """Best-effort update of the durable project cost aggregate.

        No-op when the record has no ``project_id`` or no repository
        is configured.  Failures are logged at WARNING and swallowed.
        """
        if self._project_cost_repo is None or cost_record.project_id is None:
            return

        try:
            await self._project_cost_repo.increment(
                cost_record.project_id,
                cost_record.cost_usd,
                cost_record.input_tokens,
                cost_record.output_tokens,
            )
            logger.debug(
                BUDGET_PROJECT_COST_AGGREGATED,
                project_id=cost_record.project_id,
                cost_usd=cost_record.cost_usd,
            )
        except MemoryError, RecursionError:
            raise
        except Exception:
            logger.warning(
                BUDGET_PROJECT_COST_AGGREGATION_FAILED,
                project_id=cost_record.project_id,
                cost_usd=cost_record.cost_usd,
                exc_info=True,
            )

    async def _snapshot(
        self,
        *,
        now: datetime | None = None,
    ) -> tuple[CostRecord, ...]:
        """Return an immutable snapshot of all current records.

        When the record count exceeds the auto-prune threshold,
        expired records are removed before the snapshot is taken.

        Args:
            now: Reference time for auto-prune cutoff.  Defaults to
                current UTC time.
        """
        async with self._lock:
            if len(self._records) > self._auto_prune_threshold:
                ref = now or datetime.now(UTC)
                cutoff = ref - timedelta(hours=_COST_WINDOW_HOURS)
                pruned = self._prune_before(cutoff)
                if pruned:
                    logger.info(
                        BUDGET_RECORDS_AUTO_PRUNED,
                        pruned=pruned,
                        remaining=len(self._records),
                    )
            return tuple(self._records)

    def _prune_before(self, cutoff: datetime) -> int:
        """Remove records older than *cutoff*.  Caller must hold ``_lock``."""
        if not self._records:
            return 0
        before = len(self._records)
        self._records = [r for r in self._records if r.timestamp >= cutoff]
        return before - len(self._records)

    def _build_dept_spendings(
        self,
        agent_spendings: list[AgentSpending],
    ) -> list[DepartmentSpending]:
        """Aggregate per-department spending from agent spendings."""
        dept_map: dict[str, list[AgentSpending]] = defaultdict(list)
        for agent_spend in agent_spendings:
            dept = self._resolve_department(agent_spend.agent_id)
            if dept is not None:
                dept_map[dept].append(agent_spend)

        return [
            DepartmentSpending(
                department_name=dname,
                total_cost_usd=round(
                    math.fsum(s.total_cost_usd for s in spends),
                    BUDGET_ROUNDING_PRECISION,
                ),
                total_input_tokens=sum(s.total_input_tokens for s in spends),
                total_output_tokens=sum(s.total_output_tokens for s in spends),
                record_count=sum(s.record_count for s in spends),
            )
            for dname, spends in sorted(dept_map.items())
        ]

    def _build_budget_context(
        self,
        total_cost: float,
    ) -> tuple[float, float, BudgetAlertLevel]:
        """Compute budget monthly, used percentage, and alert level."""
        budget_monthly = (
            self._budget_config.total_monthly if self._budget_config else 0.0
        )
        used_pct = (
            round(
                total_cost / budget_monthly * 100,
                BUDGET_ROUNDING_PRECISION,
            )
            if budget_monthly > 0
            else 0.0
        )
        alert = self._compute_alert_level(used_pct)
        return budget_monthly, used_pct, alert

    def _compute_alert_level(self, used_pct: float) -> BudgetAlertLevel:
        """Determine alert level from the rounded budget percentage."""
        if self._budget_config is None or self._budget_config.total_monthly <= 0:
            return BudgetAlertLevel.NORMAL

        alerts = self._budget_config.alerts

        if used_pct >= alerts.hard_stop_at:
            return BudgetAlertLevel.HARD_STOP
        if used_pct >= alerts.critical_at:
            return BudgetAlertLevel.CRITICAL
        if used_pct >= alerts.warn_at:
            return BudgetAlertLevel.WARNING
        return BudgetAlertLevel.NORMAL

    def _resolve_department(self, agent_id: str) -> str | None:
        """Resolve agent to department, logging resolver errors."""
        if self._department_resolver is None:
            return None
        try:
            return self._department_resolver(agent_id)
        except MemoryError, RecursionError:
            raise
        except Exception as exc:
            logger.warning(
                BUDGET_DEPARTMENT_RESOLVE_FAILED,
                agent_id=agent_id,
                error=str(exc),
                error_type=type(exc).__qualname__,
            )
            return None


# ── Module-level pure helpers ────────────────────────────────────


def _validate_time_range(
    start: datetime | None,
    end: datetime | None,
) -> None:
    """Raise ``ValueError`` if *start* >= *end* when both are given."""
    if start is not None and end is not None and start >= end:
        logger.warning(
            BUDGET_TIME_RANGE_INVALID,
            start=start.isoformat(),
            end=end.isoformat(),
        )
        msg = f"start ({start.isoformat()}) must be before end ({end.isoformat()})"
        raise ValueError(msg)


def _filter_records(  # noqa: PLR0913
    records: Sequence[CostRecord],
    *,
    agent_id: str | None = None,
    task_id: str | None = None,
    project_id: str | None = None,
    provider: NotBlankStr | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
) -> tuple[CostRecord, ...]:
    """Filter records by agent, task, project, provider, and/or time range.

    Time semantics: ``start <= timestamp < end``.
    """
    return tuple(
        r
        for r in records
        if (agent_id is None or r.agent_id == agent_id)
        and (task_id is None or r.task_id == task_id)
        and (project_id is None or r.project_id == project_id)
        and (provider is None or r.provider == provider)
        and (start is None or r.timestamp >= start)
        and (end is None or r.timestamp < end)
    )


def _build_agent_spendings(
    filtered: Sequence[CostRecord],
) -> list[AgentSpending]:
    """Group filtered records by agent and aggregate each group."""
    by_agent: dict[str, list[CostRecord]] = defaultdict(list)
    for rec in filtered:
        by_agent[rec.agent_id].append(rec)

    result: list[AgentSpending] = []
    for aid in sorted(by_agent):
        agg = _aggregate(by_agent[aid])
        result.append(
            AgentSpending(
                agent_id=aid,
                total_cost_usd=agg.cost,
                total_input_tokens=agg.input_tokens,
                total_output_tokens=agg.output_tokens,
                record_count=agg.record_count,
            )
        )
    return result


def _aggregate(
    records: Sequence[CostRecord],
) -> _AggregateResult:
    """Aggregate records into cost, token totals, and count."""
    costs: list[float] = []
    input_tokens = 0
    output_tokens = 0
    for r in records:
        costs.append(r.cost_usd)
        input_tokens += r.input_tokens
        output_tokens += r.output_tokens
    cost = round(math.fsum(costs), BUDGET_ROUNDING_PRECISION)
    return _AggregateResult(cost, input_tokens, output_tokens, len(costs))
