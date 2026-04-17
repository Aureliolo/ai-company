"""Process-global accessor for the active :class:`PrometheusCollector`.

Startup wiring stashes the ``AppState``-owned collector here so call
sites far from ``AppState`` (the cost-recording helper in
:mod:`synthorg.engine.cost_recording`, the tool invocation bridge,
the task engine) can emit provider / task / tool metrics without
needing an async-safe reference back through the dependency graph.

The collector is held behind a weak reference so tests that tear
down ``AppState`` between cases do not keep a dead instance live and
do not accidentally record metrics against the previous run.

``record_*`` wrappers no-op when no collector is registered, so
call sites remain safe even when metrics are disabled.
"""

import weakref
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from synthorg.observability.prometheus_collector import PrometheusCollector

_collector_ref: weakref.ReferenceType[PrometheusCollector] | None = None


def set_active_collector(collector: PrometheusCollector) -> None:
    """Register *collector* as the process-active Prometheus collector.

    Idempotent when called with the same instance; overwriting with
    a different instance is expected between tests.
    """
    global _collector_ref  # noqa: PLW0603
    _collector_ref = weakref.ref(collector)


def clear_active_collector() -> None:
    """Drop the process-active collector reference."""
    global _collector_ref  # noqa: PLW0603
    _collector_ref = None


def _active() -> PrometheusCollector | None:
    if _collector_ref is None:
        return None
    return _collector_ref()


def record_provider_usage(
    *,
    provider: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    cost_usd: float,
) -> None:
    """Forward to :meth:`PrometheusCollector.record_provider_usage`.

    No-op when no collector is registered so call sites can emit
    metrics without a guard.
    """
    collector = _active()
    if collector is None:
        return
    collector.record_provider_usage(
        provider=provider,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost_usd,
    )


def record_task_run(*, outcome: str, duration_sec: float) -> None:
    """Forward to :meth:`PrometheusCollector.record_task_run`."""
    collector = _active()
    if collector is None:
        return
    collector.record_task_run(outcome=outcome, duration_sec=duration_sec)


def record_security_verdict(verdict: str) -> None:
    """Forward to :meth:`PrometheusCollector.record_security_verdict`."""
    collector = _active()
    if collector is None:
        return
    collector.record_security_verdict(verdict)
