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
handler returns a structured ``not_supported`` envelope with a stable
reason.  The MCP tool surface stays registered, the placeholder log
noise remains visible to ops, and the handler signature + test shape
match the other domains so the facade can drop in without touching
the MCP layer.
"""

from types import MappingProxyType
from typing import TYPE_CHECKING, Any

from synthorg.meta.mcp.handlers.common import not_supported

if TYPE_CHECKING:
    from collections.abc import Mapping

    from synthorg.meta.mcp.invoker import ToolHandler

_WHY_SIGNALS = (
    "signal aggregators live inside SelfImprovementService; no "
    "SignalsService facade is attached to app_state yet"
)
_WHY_PROPOSALS = (
    "proposal store + guard chain submission is orchestrated through "
    "the self-improvement cycle; no standalone submit entry point is "
    "exposed on app_state"
)


async def _signals_get_org_snapshot(
    *,
    app_state: Any,  # noqa: ARG001
    arguments: dict[str, Any],  # noqa: ARG001
    actor: Any = None,  # noqa: ARG001
) -> str:
    return not_supported("synthorg_signals_get_org_snapshot", _WHY_SIGNALS)


async def _signals_get_performance(
    *,
    app_state: Any,  # noqa: ARG001
    arguments: dict[str, Any],  # noqa: ARG001
    actor: Any = None,  # noqa: ARG001
) -> str:
    return not_supported("synthorg_signals_get_performance", _WHY_SIGNALS)


async def _signals_get_budget(
    *,
    app_state: Any,  # noqa: ARG001
    arguments: dict[str, Any],  # noqa: ARG001
    actor: Any = None,  # noqa: ARG001
) -> str:
    return not_supported("synthorg_signals_get_budget", _WHY_SIGNALS)


async def _signals_get_coordination(
    *,
    app_state: Any,  # noqa: ARG001
    arguments: dict[str, Any],  # noqa: ARG001
    actor: Any = None,  # noqa: ARG001
) -> str:
    return not_supported("synthorg_signals_get_coordination", _WHY_SIGNALS)


async def _signals_get_scaling_history(
    *,
    app_state: Any,  # noqa: ARG001
    arguments: dict[str, Any],  # noqa: ARG001
    actor: Any = None,  # noqa: ARG001
) -> str:
    return not_supported("synthorg_signals_get_scaling_history", _WHY_SIGNALS)


async def _signals_get_error_patterns(
    *,
    app_state: Any,  # noqa: ARG001
    arguments: dict[str, Any],  # noqa: ARG001
    actor: Any = None,  # noqa: ARG001
) -> str:
    return not_supported("synthorg_signals_get_error_patterns", _WHY_SIGNALS)


async def _signals_get_evolution_outcomes(
    *,
    app_state: Any,  # noqa: ARG001
    arguments: dict[str, Any],  # noqa: ARG001
    actor: Any = None,  # noqa: ARG001
) -> str:
    return not_supported("synthorg_signals_get_evolution_outcomes", _WHY_SIGNALS)


async def _signals_get_proposals(
    *,
    app_state: Any,  # noqa: ARG001
    arguments: dict[str, Any],  # noqa: ARG001
    actor: Any = None,  # noqa: ARG001
) -> str:
    return not_supported("synthorg_signals_get_proposals", _WHY_PROPOSALS)


async def _signals_submit_proposal(
    *,
    app_state: Any,  # noqa: ARG001
    arguments: dict[str, Any],  # noqa: ARG001
    actor: Any = None,  # noqa: ARG001
) -> str:
    return not_supported("synthorg_signals_submit_proposal", _WHY_PROPOSALS)


SIGNAL_HANDLERS: Mapping[str, ToolHandler] = MappingProxyType(
    {
        "synthorg_signals_get_org_snapshot": _signals_get_org_snapshot,
        "synthorg_signals_get_performance": _signals_get_performance,
        "synthorg_signals_get_budget": _signals_get_budget,
        "synthorg_signals_get_coordination": _signals_get_coordination,
        "synthorg_signals_get_scaling_history": _signals_get_scaling_history,
        "synthorg_signals_get_error_patterns": _signals_get_error_patterns,
        "synthorg_signals_get_evolution_outcomes": _signals_get_evolution_outcomes,
        "synthorg_signals_get_proposals": _signals_get_proposals,
        "synthorg_signals_submit_proposal": _signals_submit_proposal,
    },
)
