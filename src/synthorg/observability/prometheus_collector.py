"""Prometheus metrics collector for SynthOrg business metrics.

Maintains Gauge/Counter instances in a dedicated ``CollectorRegistry``
and refreshes them from AppState services at scrape time.  The
``/metrics`` endpoint calls :meth:`refresh` before generating output.

Coordination metrics (efficiency, overhead) are push-updated by the
coordination collector after each multi-agent execution -- they are
not refreshed on scrape.
"""

import asyncio
from calendar import monthrange
from collections import Counter
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from prometheus_client import CollectorRegistry, Gauge, Info
from prometheus_client import Counter as PromCounter

from synthorg import __version__
from synthorg.observability import get_logger
from synthorg.observability.events.metrics import (
    METRICS_COLLECTOR_INITIALIZED,
    METRICS_COORDINATION_RECORDED,
    METRICS_SCRAPE_COMPLETED,
    METRICS_SCRAPE_FAILED,
)

if TYPE_CHECKING:
    from synthorg.api.state import AppState

logger = get_logger(__name__)


class PrometheusCollector:
    """Collects business metrics from SynthOrg services for Prometheus.

    Uses a dedicated ``CollectorRegistry`` to avoid polluting the global
    default registry.  Most metric values are refreshed on each scrape
    via :meth:`refresh` (pull model).  Coordination metrics are
    push-updated by :meth:`record_coordination_metrics` after each
    multi-agent execution; security verdicts are push-updated by
    :meth:`record_security_verdict`.

    Args:
        prefix: Metric name prefix (default ``"synthorg"``).
    """

    def __init__(self, *, prefix: str = "synthorg") -> None:
        self._prefix = prefix
        self.registry = CollectorRegistry()

        # -- Info --------------------------------------------------------
        self._info = Info(
            f"{prefix}_app",
            "SynthOrg application info",
            registry=self.registry,
        )
        self._info.info({"version": __version__})

        # -- Agent gauges ------------------------------------------------
        self._agents_total = Gauge(
            f"{prefix}_active_agents_total",
            "Number of active agents",
            ["status", "trust_level"],
            registry=self.registry,
        )

        # -- Task gauges -------------------------------------------------
        self._tasks_total = Gauge(
            f"{prefix}_tasks_total",
            "Number of tasks by status and agent",
            ["status", "agent"],
            registry=self.registry,
        )

        # -- Cost gauges -------------------------------------------------
        self._cost_total = Gauge(
            f"{prefix}_cost_total",
            "Total accumulated cost",
            registry=self.registry,
        )

        # -- Budget gauges -----------------------------------------------
        self._budget_used_percent = Gauge(
            f"{prefix}_budget_used_percent",
            "Accumulated cost as percentage of monthly budget limit",
            registry=self.registry,
        )
        self._budget_monthly_usd = Gauge(
            f"{prefix}_budget_monthly_usd",
            "Monthly budget limit in USD",
            registry=self.registry,
        )
        self._budget_daily_used_percent = Gauge(
            f"{prefix}_budget_daily_used_percent",
            "Daily cost as percentage of prorated daily budget",
            registry=self.registry,
        )

        # -- Per-agent cost gauges ---------------------------------------
        self._agent_cost_total = Gauge(
            f"{prefix}_agent_cost_total",
            "Per-agent accumulated cost in USD",
            ["agent_id"],
            registry=self.registry,
        )
        self._agent_budget_used_percent = Gauge(
            f"{prefix}_agent_budget_used_percent",
            "Per-agent daily cost as percentage of per-agent daily limit",
            ["agent_id"],
            registry=self.registry,
        )

        # -- Coordination gauges (push-updated) --------------------------
        self._coordination_efficiency = Gauge(
            f"{prefix}_coordination_efficiency",
            "Coordination efficiency ratio",
            registry=self.registry,
        )
        self._coordination_overhead_percent = Gauge(
            f"{prefix}_coordination_overhead_percent",
            "Coordination overhead percentage",
            registry=self.registry,
        )

        # -- Security counters -------------------------------------------
        self._security_evaluations = PromCounter(
            f"{prefix}_security_evaluations_total",
            "Security evaluation verdicts",
            ["verdict"],
            registry=self.registry,
        )

        logger.debug(METRICS_COLLECTOR_INITIALIZED, prefix=prefix)

    # Bounded set of valid verdicts to prevent label cardinality explosion.
    _VALID_VERDICTS = frozenset({"allow", "deny", "escalate", "output_scan"})

    def record_security_verdict(self, verdict: str) -> None:
        """Increment the security verdict counter.

        Called by a thin hook around ``SecOpsService.evaluate_pre_tool()``.

        Args:
            verdict: The verdict string -- one of ``"allow"``,
                ``"deny"``, ``"escalate"``, or ``"output_scan"``
                (see ``_VALID_VERDICTS``).

        Raises:
            ValueError: If *verdict* is not in the allowed set.
        """
        if verdict not in self._VALID_VERDICTS:
            msg = (
                f"Unknown security verdict {verdict!r}; "
                f"expected one of {sorted(self._VALID_VERDICTS)}"
            )
            logger.warning(
                METRICS_SCRAPE_FAILED,
                component="security_verdict",
                verdict=verdict,
                expected=sorted(self._VALID_VERDICTS),
            )
            raise ValueError(msg)
        self._security_evaluations.labels(verdict=verdict).inc()

    def record_coordination_metrics(
        self,
        *,
        efficiency: float,
        overhead_percent: float,
    ) -> None:
        """Update coordination gauges after a multi-agent execution.

        Called by ``CoordinationCollector`` post-execution.

        Args:
            efficiency: Coordination efficiency ratio (0.0-1.0).
            overhead_percent: Coordination overhead percentage.
        """
        self._coordination_efficiency.set(efficiency)
        self._coordination_overhead_percent.set(overhead_percent)
        logger.debug(
            METRICS_COORDINATION_RECORDED,
            efficiency=efficiency,
            overhead_percent=overhead_percent,
        )

    async def refresh(self, app_state: AppState) -> None:
        """Refresh all gauge values from AppState services.

        Each service query is wrapped individually so a failure in one
        does not prevent other metrics from updating.

        Args:
            app_state: The application state containing service references.
        """
        # Fetch total + daily cost once and share across metrics.
        total_cost: float | None = None
        daily_cost: float | None = None
        utc_midnight = datetime.now(UTC).replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )
        if app_state.has_cost_tracker:
            try:
                total_cost = await app_state.cost_tracker.get_total_cost()
                daily_cost = await app_state.cost_tracker.get_total_cost(
                    start=utc_midnight,
                )
            except MemoryError, RecursionError:
                raise
            except Exception:
                logger.warning(
                    METRICS_SCRAPE_FAILED,
                    component="cost_tracker",
                    exc_info=True,
                )
        self._refresh_cost_gauge(total_cost)
        self._refresh_budget_metrics(app_state, total_cost)
        self._refresh_daily_budget_metric(app_state, daily_cost)
        agents = await self._refresh_agent_metrics(app_state)
        await self._refresh_agent_cost_metrics(
            app_state,
            agents,
            utc_midnight,
        )
        await self._refresh_task_metrics(app_state)
        logger.debug(METRICS_SCRAPE_COMPLETED)

    def _refresh_cost_gauge(self, total_cost: float | None) -> None:
        """Update cost gauge from a pre-fetched total."""
        if total_cost is not None:
            self._cost_total.set(total_cost)

    def _refresh_budget_metrics(
        self,
        app_state: AppState,
        total_cost: float | None,
    ) -> None:
        """Update budget utilization gauges from CostTracker config."""
        if not app_state.has_cost_tracker:
            return
        try:
            tracker = app_state.cost_tracker
            if tracker.budget_config is None:
                return
            monthly = tracker.budget_config.total_monthly
            self._budget_monthly_usd.set(monthly)
            if monthly > 0 and total_cost is not None:
                self._budget_used_percent.set(
                    min(100.0, (total_cost / monthly) * 100.0),
                )
        except MemoryError, RecursionError:
            raise
        except Exception:
            logger.warning(
                METRICS_SCRAPE_FAILED,
                component="budget",
                exc_info=True,
            )

    def _refresh_daily_budget_metric(
        self,
        app_state: AppState,
        daily_cost: float | None,
    ) -> None:
        """Update daily budget utilization gauge.

        Computes ``daily_cost / (total_monthly / days_in_month) * 100``,
        capped at 100%.  Returns early without updating if cost tracker
        is unavailable, *daily_cost* is ``None``, budget config is
        missing, or the monthly budget is zero or negative.

        Args:
            app_state: The application state containing cost tracker.
            daily_cost: Cost accumulated since UTC midnight, or ``None``
                if unavailable.
        """
        if not app_state.has_cost_tracker or daily_cost is None:
            self._budget_daily_used_percent.set(0.0)
            return
        try:
            tracker = app_state.cost_tracker
            if tracker.budget_config is None:
                self._budget_daily_used_percent.set(0.0)
                return
            monthly = tracker.budget_config.total_monthly
            if monthly <= 0:
                self._budget_daily_used_percent.set(0.0)
                return
            now = datetime.now(UTC)
            days = monthrange(now.year, now.month)[1]
            daily_budget = monthly / days
            self._budget_daily_used_percent.set(
                min(100.0, (daily_cost / daily_budget) * 100.0),
            )
        except MemoryError, RecursionError:
            raise
        except Exception:
            logger.warning(
                METRICS_SCRAPE_FAILED,
                component="daily_budget",
                exc_info=True,
            )

    async def _refresh_agent_metrics(
        self,
        app_state: AppState,
    ) -> tuple[Any, ...]:
        """Update agent gauges from AgentRegistryService.

        Queries active agents and aggregates counts by
        ``(status, trust_level)``.  Clears all existing label series
        before setting new ones so that disappeared combinations drop
        to zero instead of retaining stale values.

        Args:
            app_state: The application state containing agent registry.

        Returns:
            Tuple of active agent objects (empty tuple if the agent
            registry is unavailable or a service error occurs).
        """
        if not app_state.has_agent_registry:
            return ()
        try:
            agents = await app_state.agent_registry.list_active()
            counts: Counter[tuple[str, str]] = Counter()
            for agent in agents:
                status = str(agent.status)
                trust = str(agent.tools.access_level)
                counts[(status, trust)] += 1
            # Clear stale label series so disappeared combinations
            # drop to zero instead of retaining previous values.
            self._agents_total.clear()
            for (status, trust), count in counts.items():
                self._agents_total.labels(
                    status=status,
                    trust_level=trust,
                ).set(count)
            return tuple(agents)
        except MemoryError, RecursionError:
            raise
        except Exception:
            logger.warning(
                METRICS_SCRAPE_FAILED,
                component="agent_registry",
                exc_info=True,
            )
            return ()

    async def _refresh_agent_cost_metrics(
        self,
        app_state: AppState,
        agents: tuple[Any, ...],
        utc_midnight: datetime,
    ) -> None:
        """Update per-agent cost and budget utilization gauges.

        Always clears gauge label series first so disappeared agents
        are dropped.  Then returns early if *agents* is empty or the
        cost tracker is unavailable; otherwise queries cumulative and
        daily costs per agent.

        Args:
            app_state: The application state containing cost tracker.
            agents: Pre-fetched active agents from the agent registry.
            utc_midnight: Start of the current UTC day for daily cost
                queries.
        """
        self._agent_cost_total.clear()
        self._agent_budget_used_percent.clear()
        if not agents or not app_state.has_cost_tracker:
            return
        try:
            tracker = app_state.cost_tracker
            budget_cfg = tracker.budget_config
            per_agent_limit = (
                budget_cfg.per_agent_daily_limit
                if budget_cfg is not None and budget_cfg.total_monthly > 0
                else 0.0
            )
            agent_ids = [str(a.id) for a in agents]
            # Fan-out cost queries in parallel.
            total_tasks: dict[str, asyncio.Task[float]] = {}
            daily_tasks: dict[str, asyncio.Task[float]] = {}
            async with asyncio.TaskGroup() as tg:
                for aid in agent_ids:
                    total_tasks[aid] = tg.create_task(
                        tracker.get_agent_cost(aid),
                    )
                    if per_agent_limit > 0:
                        daily_tasks[aid] = tg.create_task(
                            tracker.get_agent_cost(
                                aid,
                                start=utc_midnight,
                            ),
                        )
            for aid in agent_ids:
                self._agent_cost_total.labels(agent_id=aid).set(
                    total_tasks[aid].result(),
                )
                if per_agent_limit > 0:
                    daily = daily_tasks[aid].result()
                    pct = min(
                        100.0,
                        (daily / per_agent_limit) * 100.0,
                    )
                    self._agent_budget_used_percent.labels(
                        agent_id=aid,
                    ).set(pct)
        except MemoryError, RecursionError:
            raise
        except Exception:
            logger.warning(
                METRICS_SCRAPE_FAILED,
                component="agent_cost",
                exc_info=True,
            )

    async def _refresh_task_metrics(self, app_state: AppState) -> None:
        """Update task gauges from TaskEngine."""
        if not app_state.has_task_engine:
            return
        try:
            tasks, _ = await app_state.task_engine.list_tasks()
            counts: Counter[tuple[str, str]] = Counter()
            for task in tasks:
                status = str(task.status)
                agent = str(task.assigned_to) if task.assigned_to else ""
                counts[(status, agent)] += 1
            self._tasks_total.clear()
            for (status, agent), count in counts.items():
                self._tasks_total.labels(
                    status=status,
                    agent=agent,
                ).set(count)
        except MemoryError, RecursionError:
            raise
        except Exception:
            logger.warning(
                METRICS_SCRAPE_FAILED,
                component="task_engine",
                exc_info=True,
            )
