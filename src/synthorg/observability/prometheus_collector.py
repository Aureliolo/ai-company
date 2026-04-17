"""Prometheus metrics collector for SynthOrg business metrics.

Maintains Gauge/Counter instances in a dedicated ``CollectorRegistry``
and refreshes them from AppState services at scrape time.  The
``/metrics`` endpoint calls :meth:`refresh` before generating output.

Coordination metrics (efficiency, overhead) are push-updated by the
coordination collector after each multi-agent execution -- they are
not refreshed on scrape.
"""

import asyncio
from collections import Counter
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from prometheus_client import CollectorRegistry, Gauge, Histogram, Info
from prometheus_client import Counter as PromCounter

from synthorg import __version__
from synthorg.budget.billing import billing_period_start
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


def _status_class(status_code: int) -> str:
    """Map an HTTP status code to its Nxx class label.

    Returns a string outside ``_VALID_STATUS_CLASSES`` on
    out-of-range input so the caller's guard raises clearly rather
    than silently bucketing garbage into ``"5xx"``.
    """
    if 100 <= status_code < 600:  # noqa: PLR2004
        return f"{status_code // 100}xx"
    return "invalid"


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

        # -- Provider token/cost counters (push-updated per LLM call) ----
        self._provider_tokens = PromCounter(
            f"{prefix}_provider_tokens_total",
            "Tokens consumed per provider, model, and direction",
            ["provider", "model", "direction"],
            registry=self.registry,
        )
        self._provider_cost_usd = PromCounter(
            f"{prefix}_provider_cost_usd_total",
            "Accumulated cost in USD per provider and model",
            ["provider", "model"],
            registry=self.registry,
        )

        # -- API request histogram (push-updated by middleware) ----------
        self._api_request_duration = Histogram(
            f"{prefix}_api_request_duration_seconds",
            "HTTP request handler duration",
            ["method", "route", "status_class"],
            buckets=(
                0.005,
                0.01,
                0.025,
                0.05,
                0.1,
                0.25,
                0.5,
                1.0,
                2.5,
                5.0,
                10.0,
            ),
            registry=self.registry,
        )

        # -- Task counters + histogram (push-updated by observer) --------
        self._task_runs = PromCounter(
            f"{prefix}_task_runs_total",
            "Task completions by outcome",
            ["outcome"],
            registry=self.registry,
        )
        self._task_duration = Histogram(
            f"{prefix}_task_duration_seconds",
            "Task execution duration by outcome",
            ["outcome"],
            buckets=(0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0, 300.0, 600.0),
            registry=self.registry,
        )

        # -- Tool counters + histogram (push-updated by invoker) ---------
        self._tool_invocations = PromCounter(
            f"{prefix}_tool_invocations_total",
            "Tool invocation count by tool and outcome",
            ["tool_name", "outcome"],
            registry=self.registry,
        )
        self._tool_duration = Histogram(
            f"{prefix}_tool_duration_seconds",
            "Tool invocation duration by tool and outcome",
            ["tool_name", "outcome"],
            buckets=(0.005, 0.025, 0.1, 0.5, 1.0, 5.0, 30.0, 120.0),
            registry=self.registry,
        )

        # -- Audit chain metrics (push-updated by audit sink) ------------
        self._audit_chain_appends = PromCounter(
            f"{prefix}_audit_chain_appends_total",
            "Audit chain append operations by status",
            ["status"],
            registry=self.registry,
        )
        self._audit_chain_depth = Gauge(
            f"{prefix}_audit_chain_depth",
            "Current audit hash chain length",
            registry=self.registry,
        )
        self._audit_chain_last_append_ts = Gauge(
            f"{prefix}_audit_chain_last_append_timestamp_seconds",
            "Unix timestamp of the last audit chain append",
            registry=self.registry,
        )

        # -- OTLP export health (push-updated by OTLP handlers) ----------
        self._otlp_export_batches = PromCounter(
            f"{prefix}_otlp_export_batches_total",
            "OTLP export batches by kind and outcome",
            ["kind", "outcome"],
            registry=self.registry,
        )
        self._otlp_export_dropped = PromCounter(
            f"{prefix}_otlp_export_dropped_records_total",
            "OTLP records dropped (queue full, export failed past retries)",
            ["kind"],
            registry=self.registry,
        )

        logger.debug(METRICS_COLLECTOR_INITIALIZED, prefix=prefix)

    # Bounded set of valid verdicts to prevent label cardinality explosion.
    _VALID_VERDICTS = frozenset({"allow", "deny", "escalate", "output_scan"})

    # Bounded label sets for outcome/direction/status_class labels.
    _VALID_TOKEN_DIRECTIONS = frozenset({"input", "output"})
    _VALID_TASK_OUTCOMES = frozenset({"succeeded", "failed", "cancelled"})
    _VALID_TOOL_OUTCOMES = frozenset({"success", "error", "timeout"})
    _VALID_STATUS_CLASSES = frozenset({"1xx", "2xx", "3xx", "4xx", "5xx"})
    _VALID_AUDIT_APPEND_STATUSES = frozenset({"signed", "fallback", "error"})
    _VALID_OTLP_KINDS = frozenset({"logs", "traces"})
    _VALID_OTLP_OUTCOMES = frozenset({"success", "failure"})

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

    def record_provider_usage(
        self,
        *,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float,
    ) -> None:
        """Record an LLM provider call's token and cost usage.

        Called from ``integration/provider_caller.py`` after a
        completion resolves (after retry/rate-limit). Tokens and cost
        are monotonically increasing counters -- never reset at
        runtime.

        Args:
            provider: Provider id (e.g. ``"example-provider"``).
            model: Model name (e.g. ``"large"``).
            input_tokens: Tokens in the request prompt.
            output_tokens: Tokens in the response completion.
            cost_usd: Computed cost in USD for this call.
        """
        if input_tokens < 0 or output_tokens < 0 or cost_usd < 0:
            msg = "record_provider_usage: token counts and cost must be non-negative"
            raise ValueError(msg)
        self._provider_tokens.labels(
            provider=provider,
            model=model,
            direction="input",
        ).inc(input_tokens)
        self._provider_tokens.labels(
            provider=provider,
            model=model,
            direction="output",
        ).inc(output_tokens)
        self._provider_cost_usd.labels(
            provider=provider,
            model=model,
        ).inc(cost_usd)

    def record_api_request(
        self,
        *,
        method: str,
        route: str,
        status_code: int,
        duration_sec: float,
    ) -> None:
        """Record an HTTP request handler's duration.

        Called from ``RequestLoggingMiddleware`` (``api/middleware.py``)
        once the response is fully constructed. ``route`` is a route
        template (e.g. ``"/agents/{agent_id}"``), never a raw path --
        the middleware resolves this via ``scope["route_handler"]``.

        Args:
            method: HTTP method (uppercase, e.g. ``"GET"``).
            route: Route template string; ``"__unmatched__"`` for 404s.
            status_code: Response status code (100-599).
            duration_sec: Wall-clock duration in seconds.
        """
        status_class = _status_class(status_code)
        if status_class not in self._VALID_STATUS_CLASSES:
            msg = f"record_api_request: invalid status_code {status_code!r}"
            raise ValueError(msg)
        if duration_sec < 0:
            msg = "record_api_request: duration_sec must be non-negative"
            raise ValueError(msg)
        self._api_request_duration.labels(
            method=method,
            route=route,
            status_class=status_class,
        ).observe(duration_sec)

    def record_task_run(
        self,
        *,
        outcome: str,
        duration_sec: float,
    ) -> None:
        """Record a task's final outcome and runtime.

        Args:
            outcome: One of ``"succeeded"``, ``"failed"``,
                ``"cancelled"``.
            duration_sec: Wall-clock duration in seconds.

        Raises:
            ValueError: If *outcome* is not a valid value or
                ``duration_sec`` is negative.
        """
        if outcome not in self._VALID_TASK_OUTCOMES:
            msg = (
                f"Unknown task outcome {outcome!r}; expected one of "
                f"{sorted(self._VALID_TASK_OUTCOMES)}"
            )
            raise ValueError(msg)
        if duration_sec < 0:
            msg = "record_task_run: duration_sec must be non-negative"
            raise ValueError(msg)
        self._task_runs.labels(outcome=outcome).inc()
        self._task_duration.labels(outcome=outcome).observe(duration_sec)

    def record_tool_invocation(
        self,
        *,
        tool_name: str,
        outcome: str,
        duration_sec: float,
    ) -> None:
        """Record a tool invocation's outcome and runtime.

        Args:
            tool_name: Registered tool name (e.g. ``"web_search"``).
            outcome: One of ``"success"``, ``"error"``, ``"timeout"``.
            duration_sec: Wall-clock duration in seconds.

        Raises:
            ValueError: If *outcome* is not a valid value or
                ``duration_sec`` is negative.
        """
        if outcome not in self._VALID_TOOL_OUTCOMES:
            msg = (
                f"Unknown tool outcome {outcome!r}; expected one of "
                f"{sorted(self._VALID_TOOL_OUTCOMES)}"
            )
            raise ValueError(msg)
        if duration_sec < 0:
            msg = "record_tool_invocation: duration_sec must be non-negative"
            raise ValueError(msg)
        self._tool_invocations.labels(
            tool_name=tool_name,
            outcome=outcome,
        ).inc()
        self._tool_duration.labels(
            tool_name=tool_name,
            outcome=outcome,
        ).observe(duration_sec)

    def record_audit_append(
        self,
        *,
        status: str,
        chain_depth: int,
        timestamp_unix: float,
    ) -> None:
        """Record an audit chain append event.

        Args:
            status: One of ``"signed"`` (TSA granted), ``"fallback"``
                (local clock), or ``"error"``.
            chain_depth: Hash chain length after the append.
            timestamp_unix: Unix epoch seconds of the append.

        Raises:
            ValueError: If *status* is not a valid value or
                *chain_depth* is negative.
        """
        if status not in self._VALID_AUDIT_APPEND_STATUSES:
            msg = (
                f"Unknown audit append status {status!r}; expected "
                f"one of {sorted(self._VALID_AUDIT_APPEND_STATUSES)}"
            )
            raise ValueError(msg)
        if chain_depth < 0:
            msg = "record_audit_append: chain_depth must be non-negative"
            raise ValueError(msg)
        self._audit_chain_appends.labels(status=status).inc()
        self._audit_chain_depth.set(chain_depth)
        self._audit_chain_last_append_ts.set(timestamp_unix)

    def record_otlp_export(
        self,
        *,
        kind: str,
        outcome: str,
        dropped_records: int = 0,
    ) -> None:
        """Record an OTLP export batch outcome.

        Args:
            kind: ``"logs"`` or ``"traces"``.
            outcome: ``"success"`` or ``"failure"``.
            dropped_records: Count of records dropped (queue full or
                retry budget exhausted). Defaults to 0.

        Raises:
            ValueError: If *kind* or *outcome* are invalid or
                *dropped_records* is negative.
        """
        if kind not in self._VALID_OTLP_KINDS:
            msg = (
                f"Unknown OTLP kind {kind!r}; expected one of "
                f"{sorted(self._VALID_OTLP_KINDS)}"
            )
            raise ValueError(msg)
        if outcome not in self._VALID_OTLP_OUTCOMES:
            msg = (
                f"Unknown OTLP outcome {outcome!r}; expected one of "
                f"{sorted(self._VALID_OTLP_OUTCOMES)}"
            )
            raise ValueError(msg)
        if dropped_records < 0:
            msg = "record_otlp_export: dropped_records must be non-negative"
            raise ValueError(msg)
        self._otlp_export_batches.labels(kind=kind, outcome=outcome).inc()
        if dropped_records > 0:
            self._otlp_export_dropped.labels(kind=kind).inc(dropped_records)

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
        # Fetch cost snapshots once and share across metrics.
        total_cost: float | None = None
        daily_cost: float | None = None
        billing_cost: float | None = None
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
                tracker = app_state.cost_tracker
                reset_day = (
                    tracker.budget_config.reset_day
                    if tracker.budget_config is not None
                    else 1
                )
                period_start = billing_period_start(
                    reset_day,
                    now=utc_midnight,
                )
                billing_cost = await tracker.get_total_cost(
                    start=period_start,
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
        self._refresh_budget_metrics(app_state, billing_cost)
        self._refresh_daily_budget_metric(app_state, daily_cost, utc_midnight)
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
        billing_cost: float | None,
    ) -> None:
        """Update budget utilization gauges from CostTracker config.

        Args:
            app_state: The application state containing cost tracker.
            billing_cost: Cost accumulated since the start of the
                current billing period (month start), or ``None``
                if unavailable.
        """
        if not app_state.has_cost_tracker:
            self._budget_used_percent.set(0.0)
            self._budget_monthly_usd.set(0.0)
            return
        try:
            tracker = app_state.cost_tracker
            if tracker.budget_config is None:
                self._budget_used_percent.set(0.0)
                self._budget_monthly_usd.set(0.0)
                return
            monthly = tracker.budget_config.total_monthly
            self._budget_monthly_usd.set(monthly)
            if monthly > 0 and billing_cost is not None:
                self._budget_used_percent.set(
                    min(100.0, (billing_cost / monthly) * 100.0),
                )
            else:
                self._budget_used_percent.set(0.0)
        except MemoryError, RecursionError:
            raise
        except Exception:
            self._budget_used_percent.set(0.0)
            self._budget_monthly_usd.set(0.0)
            logger.warning(
                METRICS_SCRAPE_FAILED,
                component="budget",
                exc_info=True,
            )

    def _refresh_daily_budget_metric(
        self,
        app_state: AppState,
        daily_cost: float | None,
        utc_midnight: datetime,
    ) -> None:
        """Update daily budget utilization gauge.

        Computes ``daily_cost / (total_monthly / days_in_period) * 100``,
        capped at 100%, where *days_in_period* is the length of the
        current billing period (derived from ``BudgetConfig.reset_day``).
        Resets the gauge to 0.0 if cost tracker is unavailable,
        *daily_cost* is ``None``, budget config is missing, or the
        monthly budget is zero or negative.

        Args:
            app_state: The application state containing cost tracker.
            daily_cost: Cost accumulated since UTC midnight, or ``None``
                if unavailable.
            utc_midnight: Start of the current UTC day, used to derive
                the billing period boundaries for prorated budget.
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
            reset_day = tracker.budget_config.reset_day
            period_start = billing_period_start(
                reset_day,
                now=utc_midnight,
            )
            if period_start.month == 12:  # noqa: PLR2004
                next_start = period_start.replace(
                    year=period_start.year + 1,
                    month=1,
                )
            else:
                next_start = period_start.replace(
                    month=period_start.month + 1,
                )
            days_in_period = (next_start - period_start).days
            daily_budget = monthly / days_in_period
            self._budget_daily_used_percent.set(
                min(100.0, (daily_cost / daily_budget) * 100.0),
            )
        except MemoryError, RecursionError:
            raise
        except Exception:
            self._budget_daily_used_percent.set(0.0)
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

        Always clears label series first so disappeared combinations
        drop to zero.  Then returns early if the agent registry is
        unavailable; otherwise queries active agents and aggregates
        counts by ``(status, trust_level)``.

        Args:
            app_state: The application state containing agent registry.

        Returns:
            Tuple of active agent objects (empty tuple if the agent
            registry is unavailable or a service error occurs).
        """
        self._agents_total.clear()
        if not app_state.has_agent_registry:
            return ()
        try:
            agents = await app_state.agent_registry.list_active()
            counts: Counter[tuple[str, str]] = Counter()
            for agent in agents:
                status = str(agent.status)
                trust = str(agent.tools.access_level)
                counts[(status, trust)] += 1
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
        self._tasks_total.clear()
        if not app_state.has_task_engine:
            return
        try:
            tasks, _ = await app_state.task_engine.list_tasks()
            counts: Counter[tuple[str, str]] = Counter()
            for task in tasks:
                status = str(task.status)
                agent = str(task.assigned_to) if task.assigned_to else ""
                counts[(status, agent)] += 1
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
