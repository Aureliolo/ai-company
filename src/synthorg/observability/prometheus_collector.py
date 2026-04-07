"""Prometheus metrics collector for SynthOrg business metrics.

Maintains Gauge/Counter instances in a dedicated ``CollectorRegistry``
and refreshes them from AppState services at scrape time.  The
``/metrics`` endpoint calls :meth:`refresh` before generating output.
"""

from collections import Counter
from typing import TYPE_CHECKING, Any

from prometheus_client import CollectorRegistry, Gauge, Info
from prometheus_client import Counter as PromCounter

from synthorg import __version__
from synthorg.observability import get_logger
from synthorg.observability.events.metrics import (
    METRICS_COLLECTOR_INITIALIZED,
    METRICS_SCRAPE_COMPLETED,
    METRICS_SCRAPE_FAILED,
)

if TYPE_CHECKING:
    from synthorg.api.state import AppState

logger = get_logger(__name__)


class PrometheusCollector:
    """Collects business metrics from SynthOrg services for Prometheus.

    Uses a dedicated ``CollectorRegistry`` to avoid polluting the global
    default registry.  Metric values are refreshed on each scrape via
    :meth:`refresh`.

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
            f"{prefix}_agents_total",
            "Number of registered agents",
            ["status"],
            registry=self.registry,
        )

        # -- Cost gauges -------------------------------------------------
        self._cost_total = Gauge(
            f"{prefix}_cost_total",
            "Total accumulated cost",
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

    def record_security_verdict(self, verdict: str) -> None:
        """Increment the security verdict counter.

        Called by a thin hook around ``SecOpsService.evaluate_pre_tool()``.

        Args:
            verdict: The verdict string (e.g. ``"allow"``, ``"deny"``).
        """
        self._security_evaluations.labels(verdict=verdict).inc()

    async def refresh(self, app_state: AppState) -> None:
        """Refresh all gauge values from AppState services.

        Errors in individual service queries are logged and skipped --
        a failing service does not prevent other metrics from updating.

        Args:
            app_state: The application state containing service references.
        """
        try:
            await self._refresh_cost_metrics(app_state)
            await self._refresh_agent_metrics(app_state)
        except Exception:
            logger.warning(METRICS_SCRAPE_FAILED, exc_info=True)
            return

        logger.debug(METRICS_SCRAPE_COMPLETED)

    async def _refresh_cost_metrics(self, app_state: Any) -> None:
        """Update cost gauges from CostTracker."""
        if not app_state.has_cost_tracker:
            return
        try:
            total = await app_state.cost_tracker.get_total_cost()
            self._cost_total.set(total)
        except Exception:
            logger.warning(
                METRICS_SCRAPE_FAILED,
                component="cost_tracker",
                exc_info=True,
            )

    async def _refresh_agent_metrics(self, app_state: Any) -> None:
        """Update agent gauges from AgentRegistryService."""
        if not app_state.has_agent_registry:
            return
        try:
            agents = await app_state.agent_registry.list_active()
            status_counts: Counter[str] = Counter()
            for agent in agents:
                status_counts[str(agent.status)] += 1
            # Set current values for observed statuses; stale labels
            # are harmless (they report 0 until the next scrape sets them).
            for status, count in status_counts.items():
                self._agents_total.labels(status=status).set(count)
        except Exception:
            logger.warning(
                METRICS_SCRAPE_FAILED,
                component="agent_registry",
                exc_info=True,
            )
