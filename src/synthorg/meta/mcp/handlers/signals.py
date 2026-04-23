"""Signal domain MCP handlers.

9 tools backing the Chief-of-Staff agent's org-health view: org
snapshot, per-domain summaries (performance, budget, coordination,
scaling, errors, evolution), proposal listing, and proposal submission.

Upstream services (the 7 ``*SignalAggregator`` classes + ``SnapshotBuilder``
in ``synthorg.meta.signals.*`` and ``synthorg.meta.rollout.before_after``)
exist but are never exposed on ``app_state`` -- they're constructed
inside ``SelfImprovementService`` for private use during the
self-improvement cycle.  Exposing them safely requires a thin
``SignalsService`` facade that composes the aggregators with their
existing dependencies (``performance_tracker``, ``cost_tracker``,
``coordination_metrics_store``, ``scaling_service``, error taxonomy
store, evolution outcome store, telemetry collector) and a proposal
store for the write path.

Until that facade ships as its own dedicated work item, every signal
handler returns a structured ``not_supported`` envelope via the shared
:func:`_mk` factory (mirroring the ``organization`` and ``integrations``
modules); centralising on the factory keeps actor typing consistent
across the 9 handlers and removes boilerplate.
"""

from collections.abc import Mapping  # noqa: TC003 -- PEP 649 annotation
from types import MappingProxyType
from typing import TYPE_CHECKING, Any

from synthorg.meta.mcp.handler_protocol import (
    ToolHandler,  # noqa: TC001 -- PEP 649 annotation
)
from synthorg.meta.mcp.handlers.common import not_supported

if TYPE_CHECKING:
    from synthorg.core.agent import AgentIdentity

_WHY_SIGNALS = (
    "signal aggregators live inside SelfImprovementService; no "
    "SignalsService facade is attached to app_state yet"
)
_WHY_PROPOSALS = (
    "proposal store + guard chain submission is orchestrated through "
    "the self-improvement cycle; no standalone submit entry point is "
    "exposed on app_state"
)


def _mk(tool: str, why: str) -> ToolHandler:
    """Build a ``not_supported`` handler with ToolHandler-conformant typing."""

    async def handler(
        *,
        app_state: Any,  # noqa: ARG001
        arguments: dict[str, Any],  # noqa: ARG001
        actor: AgentIdentity | None = None,  # noqa: ARG001
    ) -> str:
        return not_supported(tool, why)

    return handler


SIGNAL_HANDLERS: Mapping[str, ToolHandler] = MappingProxyType(
    {
        "synthorg_signals_get_org_snapshot": _mk(
            "synthorg_signals_get_org_snapshot",
            _WHY_SIGNALS,
        ),
        "synthorg_signals_get_performance": _mk(
            "synthorg_signals_get_performance",
            _WHY_SIGNALS,
        ),
        "synthorg_signals_get_budget": _mk(
            "synthorg_signals_get_budget",
            _WHY_SIGNALS,
        ),
        "synthorg_signals_get_coordination": _mk(
            "synthorg_signals_get_coordination",
            _WHY_SIGNALS,
        ),
        "synthorg_signals_get_scaling_history": _mk(
            "synthorg_signals_get_scaling_history",
            _WHY_SIGNALS,
        ),
        "synthorg_signals_get_error_patterns": _mk(
            "synthorg_signals_get_error_patterns",
            _WHY_SIGNALS,
        ),
        "synthorg_signals_get_evolution_outcomes": _mk(
            "synthorg_signals_get_evolution_outcomes",
            _WHY_SIGNALS,
        ),
        "synthorg_signals_get_proposals": _mk(
            "synthorg_signals_get_proposals",
            _WHY_PROPOSALS,
        ),
        "synthorg_signals_submit_proposal": _mk(
            "synthorg_signals_submit_proposal",
            _WHY_PROPOSALS,
        ),
    },
)
