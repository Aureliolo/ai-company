"""Meta (self-improvement) domain MCP handlers.

5 tools.  Three are live -- ``list_mcp_tools`` reflects the registry,
``get_mcp_server_config`` returns the server metadata, and
``list_rules`` shims through :class:`CustomRulesService`.  The
remaining two (``get_config`` and ``trigger_cycle``) require facades on
``SelfImprovementService`` that have not been exposed on ``app_state``
yet, so they return a ``capability_gap`` envelope.
"""

import copy
from collections.abc import Mapping  # noqa: TC003 -- PEP 649 annotation
from types import MappingProxyType
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from synthorg.core.agent import AgentIdentity
    from synthorg.meta.rules.service import CustomRulesService

from synthorg.meta.mcp.errors import ArgumentValidationError
from synthorg.meta.mcp.handler_protocol import (
    ToolHandler,  # noqa: TC001 -- PEP 649 annotation
)
from synthorg.meta.mcp.handlers.common import (
    capability_gap,
    coerce_pagination,
    err,
    ok,
    paginate_sequence,
)
from synthorg.observability import get_logger, safe_error_description
from synthorg.observability.events.mcp import (
    MCP_HANDLER_ARGUMENT_INVALID,
    MCP_HANDLER_INVOKE_FAILED,
    MCP_HANDLER_INVOKE_SUCCESS,
    MCP_HANDLER_LAZY_SERVICE_INIT,
)

logger = get_logger(__name__)


_WHY_CONFIG = (
    "self-improvement config read requires SelfImprovementService; "
    "no facade on app_state yet"
)
_WHY_TRIGGER = (
    "improvement-cycle triggering requires SelfImprovementService; "
    "no facade on app_state yet"
)


def _log_invalid(tool: str, exc: Exception) -> None:
    logger.warning(
        MCP_HANDLER_ARGUMENT_INVALID,
        tool_name=tool,
        error_type=type(exc).__name__,
        error=safe_error_description(exc),
    )


def _log_failed(tool: str, exc: Exception) -> None:
    logger.warning(
        MCP_HANDLER_INVOKE_FAILED,
        tool_name=tool,
        error_type=type(exc).__name__,
        error=safe_error_description(exc),
    )


def _custom_rules_service(app_state: Any) -> CustomRulesService:
    """Return the custom-rules service facade.

    Prefers ``app_state.custom_rules_service`` when bootstrap has wired
    one; otherwise builds it per-call from ``app_state.persistence.
    custom_rules`` and emits ``MCP_HANDLER_LAZY_SERVICE_INIT`` so ops
    telemetry sees legacy wiring.
    """
    cached = getattr(app_state, "custom_rules_service", None)
    if cached is not None:
        return cached  # type: ignore[no-any-return]
    logger.debug(
        MCP_HANDLER_LAZY_SERVICE_INIT,
        tool_name="meta._custom_rules_service",
        service="custom_rules_service",
        reason="app_state.custom_rules_service not wired -- building per-call",
    )
    from synthorg.meta.rules.service import CustomRulesService  # noqa: PLC0415

    return CustomRulesService(repo=app_state.persistence.custom_rules)


def _rule_to_dict(rule: Any) -> dict[str, Any]:
    return {
        "id": str(rule.id),
        "name": rule.name,
        "description": rule.description,
        "metric_path": rule.metric_path,
        "comparator": rule.comparator.value,
        "threshold": rule.threshold,
        "severity": rule.severity.value,
        "target_altitudes": [a.value for a in rule.target_altitudes],
        "enabled": rule.enabled,
        "created_at": rule.created_at.isoformat(),
        "updated_at": rule.updated_at.isoformat(),
    }


async def _meta_get_config(
    *,
    app_state: Any,  # noqa: ARG001
    arguments: dict[str, Any],  # noqa: ARG001
    actor: AgentIdentity | None = None,  # noqa: ARG001
) -> str:
    return capability_gap("synthorg_meta_get_config", _WHY_CONFIG)


async def _meta_list_rules(
    *,
    app_state: Any,
    arguments: dict[str, Any],
    actor: AgentIdentity | None = None,  # noqa: ARG001
) -> str:
    tool = "synthorg_meta_list_rules"
    try:
        offset, limit = coerce_pagination(arguments)
    except ArgumentValidationError as exc:
        _log_invalid(tool, exc)
        return err(exc)
    try:
        rules = await _custom_rules_service(app_state).list_rules()
        page, meta = paginate_sequence(rules, offset=offset, limit=limit)
    except Exception as exc:
        _log_failed(tool, exc)
        return err(exc)
    logger.info(MCP_HANDLER_INVOKE_SUCCESS, tool_name=tool)
    return ok(data=[_rule_to_dict(r) for r in page], pagination=meta)


async def _meta_list_mcp_tools(
    *,
    app_state: Any,  # noqa: ARG001
    arguments: dict[str, Any],  # noqa: ARG001
    actor: AgentIdentity | None = None,  # noqa: ARG001
) -> str:
    tool = "synthorg_meta_list_mcp_tools"
    try:
        # Deferred import breaks the handlers->server->handlers import
        # cycle; kept inside the try so ImportError / circular-import
        # surfaces through the same error envelope as runtime failures.
        from synthorg.meta.mcp.server import get_registry  # noqa: PLC0415

        registry = get_registry()
        tools = list(registry.get_tool_definitions())
        response = ok(data=tools)
    except Exception as exc:
        _log_failed(tool, exc)
        return err(exc)
    logger.info(MCP_HANDLER_INVOKE_SUCCESS, tool_name=tool)
    return response


async def _meta_get_mcp_server_config(
    *,
    app_state: Any,  # noqa: ARG001
    arguments: dict[str, Any],  # noqa: ARG001
    actor: AgentIdentity | None = None,  # noqa: ARG001
) -> str:
    tool = "synthorg_meta_get_mcp_server_config"
    try:
        from synthorg.meta.mcp.server import get_server_config  # noqa: PLC0415

        config = get_server_config()
        response = ok(data=config)
    except Exception as exc:
        _log_failed(tool, exc)
        return err(exc)
    logger.info(MCP_HANDLER_INVOKE_SUCCESS, tool_name=tool)
    return response


async def _meta_trigger_cycle(
    *,
    app_state: Any,  # noqa: ARG001
    arguments: dict[str, Any],  # noqa: ARG001
    actor: AgentIdentity | None = None,  # noqa: ARG001
) -> str:
    return capability_gap("synthorg_meta_trigger_cycle", _WHY_TRIGGER)


META_HANDLERS: Mapping[str, ToolHandler] = MappingProxyType(
    copy.deepcopy(
        {
            "synthorg_meta_get_config": _meta_get_config,
            "synthorg_meta_list_rules": _meta_list_rules,
            "synthorg_meta_list_mcp_tools": _meta_list_mcp_tools,
            "synthorg_meta_get_mcp_server_config": _meta_get_mcp_server_config,
            "synthorg_meta_trigger_cycle": _meta_trigger_cycle,
        },
    ),
)
