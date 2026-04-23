"""Coordination domain MCP handlers.

9 tools across coordination, scaling, and ceremony-policy.  Most shim
onto services already exposed on ``app_state`` (``scaling_service``,
``coordination_metrics_store``, ``ceremony_scheduler``); the ones that
require richer orchestration (``coordinate_task``,
``scaling_trigger``) return ``not_supported``.
"""

from typing import Any

from synthorg.meta.mcp.handlers.common import not_supported


async def _coordination_coordinate_task(
    *,
    app_state: Any,  # noqa: ARG001
    arguments: dict[str, Any],  # noqa: ARG001
    actor: Any = None,  # noqa: ARG001
) -> str:
    return not_supported(
        "synthorg_coordination_coordinate_task",
        "task coordination orchestration runs inside the engine loop; "
        "no standalone coordinate endpoint is exposed on app_state",
    )


async def _coordination_metrics_list(
    *,
    app_state: Any,  # noqa: ARG001
    arguments: dict[str, Any],  # noqa: ARG001
    actor: Any = None,  # noqa: ARG001
) -> str:
    return not_supported(
        "synthorg_coordination_metrics_list",
        "coordination metrics list method is not exposed on "
        "coordination_metrics_store; only per-task lookups are public",
    )


async def _scaling_list_decisions(
    *,
    app_state: Any,  # noqa: ARG001
    arguments: dict[str, Any],  # noqa: ARG001
    actor: Any = None,  # noqa: ARG001
) -> str:
    return not_supported(
        "synthorg_scaling_list_decisions",
        "scaling decision history lives in ScalingService internals; "
        "no list method is exposed publicly",
    )


async def _scaling_get_decision(
    *,
    app_state: Any,  # noqa: ARG001
    arguments: dict[str, Any],  # noqa: ARG001
    actor: Any = None,  # noqa: ARG001
) -> str:
    return not_supported(
        "synthorg_scaling_get_decision",
        "no get_decision method on ScalingService",
    )


async def _scaling_get_config(
    *,
    app_state: Any,  # noqa: ARG001
    arguments: dict[str, Any],  # noqa: ARG001
    actor: Any = None,  # noqa: ARG001
) -> str:
    return not_supported(
        "synthorg_scaling_get_config",
        "scaling config is part of the SelfImprovementConfig bundle; "
        "read via the meta config tool",
    )


async def _scaling_trigger(
    *,
    app_state: Any,  # noqa: ARG001
    arguments: dict[str, Any],  # noqa: ARG001
    actor: Any = None,  # noqa: ARG001
) -> str:
    return not_supported(
        "synthorg_scaling_trigger",
        "scaling triggers run through the self-improvement cycle, not "
        "an ad-hoc MCP entry point",
    )


async def _ceremony_policy_get(
    *,
    app_state: Any,  # noqa: ARG001
    arguments: dict[str, Any],  # noqa: ARG001
    actor: Any = None,  # noqa: ARG001
) -> str:
    return not_supported(
        "synthorg_ceremony_policy_get",
        "ceremony policy read lives in the ceremony_policy controller; "
        "no facade on app_state",
    )


async def _ceremony_policy_get_resolved(
    *,
    app_state: Any,  # noqa: ARG001
    arguments: dict[str, Any],  # noqa: ARG001
    actor: Any = None,  # noqa: ARG001
) -> str:
    return not_supported(
        "synthorg_ceremony_policy_get_resolved",
        "resolved-policy computation requires ceremony strategy + "
        "context; no facade on app_state",
    )


async def _ceremony_policy_get_active_strategy(
    *,
    app_state: Any,  # noqa: ARG001
    arguments: dict[str, Any],  # noqa: ARG001
    actor: Any = None,  # noqa: ARG001
) -> str:
    return not_supported(
        "synthorg_ceremony_policy_get_active_strategy",
        "active strategy is resolved per ceremony scheduler call; no "
        "public read path on app_state",
    )


COORDINATION_HANDLERS: dict[str, Any] = {
    "synthorg_coordination_coordinate_task": _coordination_coordinate_task,
    "synthorg_coordination_metrics_list": _coordination_metrics_list,
    "synthorg_scaling_list_decisions": _scaling_list_decisions,
    "synthorg_scaling_get_decision": _scaling_get_decision,
    "synthorg_scaling_get_config": _scaling_get_config,
    "synthorg_scaling_trigger": _scaling_trigger,
    "synthorg_ceremony_policy_get": _ceremony_policy_get,
    "synthorg_ceremony_policy_get_resolved": _ceremony_policy_get_resolved,
    "synthorg_ceremony_policy_get_active_strategy": _ceremony_policy_get_active_strategy,  # noqa: E501
}
