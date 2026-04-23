"""Coordination domain MCP handlers.

9 tools across coordination, scaling, and ceremony-policy.  All nine
handlers currently return a structured ``service_fallback`` envelope via
the shared :func:`_mk` factory -- the backing services
(``scaling_service``, ``coordination_metrics_store``,
``ceremony_scheduler``) exist on ``app_state`` but none of them expose
the read-friendly facade shape the MCP tools expect, and destructive
entry points (``coordinate_task``, ``scaling_trigger``) are
orchestrated through the engine loop / self-improvement cycle rather
than an ad-hoc MCP call.  Centralising on :func:`_mk` keeps actor
typing consistent across the 9 handlers and makes wiring a future
``CoordinationService`` / ``ScalingService`` / ``CeremonyPolicyService``
facade a local change to this module.
"""

import copy
from collections.abc import Mapping  # noqa: TC003 -- PEP 649 annotation
from types import MappingProxyType
from typing import TYPE_CHECKING, Any

from synthorg.meta.mcp.handler_protocol import (
    ToolHandler,  # noqa: TC001 -- PEP 649 annotation
)
from synthorg.meta.mcp.handlers.common import service_fallback
from synthorg.observability import get_logger

if TYPE_CHECKING:
    from synthorg.core.agent import AgentIdentity

logger = get_logger(__name__)


def _mk(tool: str, why: str) -> ToolHandler:
    """Build a ``service_fallback`` handler with ToolHandler-conformant typing."""

    async def handler(
        *,
        app_state: Any,  # noqa: ARG001
        arguments: dict[str, Any],  # noqa: ARG001
        actor: AgentIdentity | None = None,  # noqa: ARG001
    ) -> str:
        return service_fallback(tool, why)

    return handler


_WHY_COORDINATE_TASK = (
    "task coordination orchestration runs inside the engine loop; no "
    "standalone coordinate endpoint is exposed on app_state"
)
_WHY_METRICS_LIST = (
    "coordination metrics list method is not exposed on "
    "coordination_metrics_store; only per-task lookups are public"
)
_WHY_SCALING_LIST = (
    "scaling decision history lives in ScalingService internals; "
    "no list method is exposed publicly"
)
_WHY_SCALING_GET = "no get_decision method on ScalingService"
_WHY_SCALING_CONFIG = (
    "scaling config is part of the SelfImprovementConfig bundle; "
    "read via the meta config tool"
)
_WHY_SCALING_TRIGGER = (
    "scaling triggers run through the self-improvement cycle, not "
    "an ad-hoc MCP entry point"
)
_WHY_CEREMONY_GET = (
    "ceremony policy read lives in the ceremony_policy controller; "
    "no facade on app_state"
)
_WHY_CEREMONY_RESOLVED = (
    "resolved-policy computation requires ceremony strategy + "
    "context; no facade on app_state"
)
_WHY_CEREMONY_ACTIVE = (
    "active strategy is resolved per ceremony scheduler call; no "
    "public read path on app_state"
)


COORDINATION_HANDLERS: Mapping[str, ToolHandler] = MappingProxyType(
    copy.deepcopy(
        {
            "synthorg_coordination_coordinate_task": _mk(
                "synthorg_coordination_coordinate_task",
                _WHY_COORDINATE_TASK,
            ),
            "synthorg_coordination_metrics_list": _mk(
                "synthorg_coordination_metrics_list",
                _WHY_METRICS_LIST,
            ),
            "synthorg_scaling_list_decisions": _mk(
                "synthorg_scaling_list_decisions",
                _WHY_SCALING_LIST,
            ),
            "synthorg_scaling_get_decision": _mk(
                "synthorg_scaling_get_decision",
                _WHY_SCALING_GET,
            ),
            "synthorg_scaling_get_config": _mk(
                "synthorg_scaling_get_config",
                _WHY_SCALING_CONFIG,
            ),
            "synthorg_scaling_trigger": _mk(
                "synthorg_scaling_trigger",
                _WHY_SCALING_TRIGGER,
            ),
            "synthorg_ceremony_policy_get": _mk(
                "synthorg_ceremony_policy_get",
                _WHY_CEREMONY_GET,
            ),
            "synthorg_ceremony_policy_get_resolved": _mk(
                "synthorg_ceremony_policy_get_resolved",
                _WHY_CEREMONY_RESOLVED,
            ),
            "synthorg_ceremony_policy_get_active_strategy": _mk(
                "synthorg_ceremony_policy_get_active_strategy",
                _WHY_CEREMONY_ACTIVE,
            ),
        },
    ),
)
