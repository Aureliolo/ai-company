"""Agent domain MCP handlers.

Shims the 18 agent tools onto the existing HR services -- ``agent_registry``
(``AgentRegistryService``), ``performance_tracker``, ``training_service``.
Tools whose underlying service surface is not yet exposed on
``app_state`` (personality registry, rich update, activity feed,
health aggregation, autonomy mutation) return a structured
``service_fallback`` envelope so the tool stays visible to ops without
pretending a service call succeeded.

Destructive ops
---------------
``synthorg_agents_delete`` enforces the full
``confirm=True`` + non-blank ``reason`` + non-``None`` ``actor`` guardrail
and emits ``MCP_DESTRUCTIVE_OP_EXECUTED`` on success.
"""

import copy
from collections.abc import Mapping  # noqa: TC003 -- PEP 649 annotation
from types import MappingProxyType
from typing import TYPE_CHECKING, Any

from synthorg.hr.errors import AgentNotFoundError
from synthorg.meta.mcp.errors import (
    ArgumentValidationError,
    GuardrailViolationError,
    invalid_argument,
)
from synthorg.meta.mcp.handler_protocol import (
    ToolHandler,  # noqa: TC001 -- PEP 649 annotation
)
from synthorg.meta.mcp.handlers.common import (
    capability_gap,
    coerce_pagination,
    dump_many,
    err,
    ok,
    paginate_sequence,
    require_arg,
    require_destructive_guardrails,
)
from synthorg.observability import get_logger, safe_error_description
from synthorg.observability.events.mcp import (
    MCP_DESTRUCTIVE_OP_EXECUTED,
    MCP_HANDLER_ARGUMENT_INVALID,
    MCP_HANDLER_GUARDRAIL_VIOLATED,
    MCP_HANDLER_INVOKE_FAILED,
    MCP_HANDLER_INVOKE_SUCCESS,
)

if TYPE_CHECKING:
    from synthorg.core.agent import AgentIdentity
    from synthorg.core.enums import AutonomyLevel

logger = get_logger(__name__)


_TY_NON_BLANK = "non-blank string"
_ARG_AGENT_NAME = "agent_name"
_ARG_AGENT_ID = "agent_id"

_WHY_CREATE = (
    "synthorg_agents_create requires the full AgentIdentity schema "
    "(personality/model/memory/tools/authority); use the hiring "
    "service API for end-to-end agent creation"
)
_WHY_UPDATE = (
    "synthorg_agents_update requires a typed diff; use the "
    "agent-identity versioning endpoints for arbitrary mutation"
)
_WHY_ACTIVITY = (
    "activity feed derivation lives in hr.activity module; no "
    "streaming endpoint on app_state"
)
_WHY_HISTORY = (
    "career history reads via agent_identity_versions controller; "
    "not exposed on app_state"
)
_WHY_HEALTH = "agent health aggregation has no dedicated service method"
_WHY_PERSONALITIES = (
    "personality registry is not exposed on app_state; personalities "
    "are stored on AgentIdentity.personality"
)
_WHY_TRAINING_LIST = (
    "training_service.execute() is the only public entry point; "
    "list/get session metadata is not materialised"
)
_WHY_TRAINING_START = (
    "training_service.execute() requires a TrainingPlan -- not "
    "representable in the current MCP tool schema"
)
_WHY_AUTONOMY_UPDATE = (
    "autonomy_level mutation goes through agent-identity evolution; "
    "no field-level mutator on agent_registry"
)
_WHY_COLLAB_CALIBRATION = (
    "collaboration calibration data is computed per-run; no direct "
    "query method on performance_tracker"
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


def _log_guardrail(tool: str, exc: GuardrailViolationError) -> None:
    logger.warning(
        MCP_HANDLER_GUARDRAIL_VIOLATED,
        tool_name=tool,
        violation=exc.violation,
    )


def _actor_id(actor: Any) -> str | None:
    """Return a stable audit identifier for ``actor`` (prefers ``.id``).

    Prefers ``actor.id`` (a ``UUID`` that never changes over the agent's
    lifetime) so destructive-op audit trails stay consistent even when
    the display name is later edited.  Falls back to ``actor.name`` only
    when id is absent.
    """
    if actor is None:
        return None
    agent_id = getattr(actor, "id", None)
    if agent_id is not None:
        return str(agent_id)
    name = getattr(actor, "name", None)
    return name if isinstance(name, str) and name else None


def _require_non_blank(arguments: dict[str, Any], key: str) -> str:
    """Extract a non-blank string argument, stripped of surrounding whitespace."""
    raw = require_arg(arguments, key, str)
    stripped = raw.strip()
    if not stripped:
        raise invalid_argument(key, _TY_NON_BLANK)
    return stripped


# --- Agent CRUD -----------------------------------------------------------


async def _agents_list(
    *,
    app_state: Any,
    arguments: dict[str, Any],
    actor: AgentIdentity | None = None,  # noqa: ARG001
) -> str:
    tool = "synthorg_agents_list"
    try:
        offset, limit = coerce_pagination(arguments)
    except ArgumentValidationError as exc:
        _log_invalid(tool, exc)
        return err(exc)
    try:
        agents = await app_state.agent_registry.list_active()
        page, meta = paginate_sequence(agents, offset=offset, limit=limit)
    except Exception as exc:
        _log_failed(tool, exc)
        return err(exc)
    logger.info(MCP_HANDLER_INVOKE_SUCCESS, tool_name=tool)
    return ok(data=dump_many(page), pagination=meta)


async def _agents_get(
    *,
    app_state: Any,
    arguments: dict[str, Any],
    actor: AgentIdentity | None = None,  # noqa: ARG001
) -> str:
    tool = "synthorg_agents_get"
    try:
        name = _require_non_blank(arguments, _ARG_AGENT_NAME)
    except ArgumentValidationError as exc:
        _log_invalid(tool, exc)
        return err(exc)
    try:
        identity = await app_state.agent_registry.get_by_name(name)
    except Exception as exc:
        _log_failed(tool, exc)
        return err(exc)
    if identity is None:
        missing = AgentNotFoundError(f"Agent {name!r} not found")
        _log_failed(tool, missing)
        return err(missing, domain_code="not_found")
    logger.info(MCP_HANDLER_INVOKE_SUCCESS, tool_name=tool)
    return ok(data=identity.model_dump(mode="json"))


async def _agents_create(
    *,
    app_state: Any,  # noqa: ARG001
    arguments: dict[str, Any],  # noqa: ARG001
    actor: AgentIdentity | None = None,  # noqa: ARG001
) -> str:
    return capability_gap("synthorg_agents_create", _WHY_CREATE)


async def _agents_update(
    *,
    app_state: Any,  # noqa: ARG001
    arguments: dict[str, Any],  # noqa: ARG001
    actor: AgentIdentity | None = None,  # noqa: ARG001
) -> str:
    return capability_gap("synthorg_agents_update", _WHY_UPDATE)


async def _agents_delete(
    *,
    app_state: Any,
    arguments: dict[str, Any],
    actor: AgentIdentity | None = None,
) -> str:
    tool = "synthorg_agents_delete"
    try:
        agent_name = _require_non_blank(arguments, _ARG_AGENT_NAME)
    except ArgumentValidationError as exc:
        _log_invalid(tool, exc)
        return err(exc)
    try:
        reason, _ = require_destructive_guardrails(arguments, actor)
    except GuardrailViolationError as exc:
        _log_guardrail(tool, exc)
        return err(exc)

    try:
        identity = await app_state.agent_registry.get_by_name(agent_name)
        if identity is None:
            missing = AgentNotFoundError(f"Agent {agent_name!r} not found")
            _log_failed(tool, missing)
            return err(missing, domain_code="not_found")
        removed = await app_state.agent_registry.unregister(str(identity.id))
    except AgentNotFoundError as exc:
        _log_failed(tool, exc)
        return err(exc, domain_code="not_found")
    except Exception as exc:
        _log_failed(tool, exc)
        return err(exc)

    logger.info(MCP_HANDLER_INVOKE_SUCCESS, tool_name=tool)
    logger.info(
        MCP_DESTRUCTIVE_OP_EXECUTED,
        tool_name=tool,
        actor_agent_id=_actor_id(actor),
        reason=reason,
        target_id=str(removed.id),
    )
    return ok(data=removed.model_dump(mode="json"))


# --- Agent observability --------------------------------------------------


async def _agents_get_performance(
    *,
    app_state: Any,
    arguments: dict[str, Any],
    actor: AgentIdentity | None = None,  # noqa: ARG001
) -> str:
    tool = "synthorg_agents_get_performance"
    try:
        agent_name = _require_non_blank(arguments, _ARG_AGENT_NAME)
    except ArgumentValidationError as exc:
        _log_invalid(tool, exc)
        return err(exc)
    try:
        identity = await app_state.agent_registry.get_by_name(agent_name)
        if identity is None:
            missing = AgentNotFoundError(f"Agent {agent_name!r} not found")
            _log_failed(tool, missing)
            return err(missing, domain_code="not_found")
        snapshot = await app_state.performance_tracker.get_snapshot(
            str(identity.id),
        )
    except Exception as exc:
        _log_failed(tool, exc)
        return err(exc)
    logger.info(MCP_HANDLER_INVOKE_SUCCESS, tool_name=tool)
    if snapshot is None:
        return ok(data=None)
    return ok(data=snapshot.model_dump(mode="json"))


async def _agents_get_activity(
    *,
    app_state: Any,  # noqa: ARG001
    arguments: dict[str, Any],  # noqa: ARG001
    actor: AgentIdentity | None = None,  # noqa: ARG001
) -> str:
    return capability_gap("synthorg_agents_get_activity", _WHY_ACTIVITY)


async def _agents_get_history(
    *,
    app_state: Any,  # noqa: ARG001
    arguments: dict[str, Any],  # noqa: ARG001
    actor: AgentIdentity | None = None,  # noqa: ARG001
) -> str:
    return capability_gap("synthorg_agents_get_history", _WHY_HISTORY)


async def _agents_get_health(
    *,
    app_state: Any,  # noqa: ARG001
    arguments: dict[str, Any],  # noqa: ARG001
    actor: AgentIdentity | None = None,  # noqa: ARG001
) -> str:
    return capability_gap("synthorg_agents_get_health", _WHY_HEALTH)


# --- Personalities --------------------------------------------------------


async def _personalities_list(
    *,
    app_state: Any,  # noqa: ARG001
    arguments: dict[str, Any],  # noqa: ARG001
    actor: AgentIdentity | None = None,  # noqa: ARG001
) -> str:
    return capability_gap("synthorg_personalities_list", _WHY_PERSONALITIES)


async def _personalities_get(
    *,
    app_state: Any,  # noqa: ARG001
    arguments: dict[str, Any],  # noqa: ARG001
    actor: AgentIdentity | None = None,  # noqa: ARG001
) -> str:
    return capability_gap("synthorg_personalities_get", _WHY_PERSONALITIES)


# --- Training -------------------------------------------------------------


async def _training_list_sessions(
    *,
    app_state: Any,  # noqa: ARG001
    arguments: dict[str, Any],  # noqa: ARG001
    actor: AgentIdentity | None = None,  # noqa: ARG001
) -> str:
    return capability_gap("synthorg_training_list_sessions", _WHY_TRAINING_LIST)


async def _training_get_session(
    *,
    app_state: Any,  # noqa: ARG001
    arguments: dict[str, Any],  # noqa: ARG001
    actor: AgentIdentity | None = None,  # noqa: ARG001
) -> str:
    return capability_gap("synthorg_training_get_session", _WHY_TRAINING_LIST)


async def _training_start_session(
    *,
    app_state: Any,  # noqa: ARG001
    arguments: dict[str, Any],  # noqa: ARG001
    actor: AgentIdentity | None = None,  # noqa: ARG001
) -> str:
    return capability_gap("synthorg_training_start_session", _WHY_TRAINING_START)


# --- Autonomy -------------------------------------------------------------


async def _autonomy_get(
    *,
    app_state: Any,
    arguments: dict[str, Any],
    actor: AgentIdentity | None = None,  # noqa: ARG001
) -> str:
    tool = "synthorg_autonomy_get"
    try:
        agent_id = _require_non_blank(arguments, _ARG_AGENT_ID)
    except ArgumentValidationError as exc:
        _log_invalid(tool, exc)
        return err(exc)
    try:
        identity = await app_state.agent_registry.get(agent_id)
    except Exception as exc:
        _log_failed(tool, exc)
        return err(exc)
    if identity is None:
        missing = AgentNotFoundError(f"Agent {agent_id!r} not found")
        _log_failed(tool, missing)
        return err(missing, domain_code="not_found")

    level: AutonomyLevel | None = identity.autonomy_level
    logger.info(MCP_HANDLER_INVOKE_SUCCESS, tool_name=tool)
    return ok(
        data={
            "agent_id": str(identity.id),
            "agent_name": str(identity.name),
            "autonomy_level": level.value if level is not None else None,
        },
    )


async def _autonomy_update(
    *,
    app_state: Any,  # noqa: ARG001
    arguments: dict[str, Any],  # noqa: ARG001
    actor: AgentIdentity | None = None,  # noqa: ARG001
) -> str:
    return capability_gap("synthorg_autonomy_update", _WHY_AUTONOMY_UPDATE)


# --- Collaboration --------------------------------------------------------


async def _collaboration_get_score(
    *,
    app_state: Any,
    arguments: dict[str, Any],
    actor: AgentIdentity | None = None,  # noqa: ARG001
) -> str:
    tool = "synthorg_collaboration_get_score"
    try:
        agent_id = _require_non_blank(arguments, _ARG_AGENT_ID)
    except ArgumentValidationError as exc:
        _log_invalid(tool, exc)
        return err(exc)
    try:
        score = await app_state.performance_tracker.get_collaboration_score(
            agent_id,
        )
    except Exception as exc:
        _log_failed(tool, exc)
        return err(exc)
    logger.info(MCP_HANDLER_INVOKE_SUCCESS, tool_name=tool)
    # ``CollaborationScoreResult`` is a Pydantic model; dump it to JSON-mode
    # primitives before handing to ``ok()`` since ``ok()`` only ``json.dumps``
    # the payload and would otherwise raise ``TypeError`` on the real tracker.
    return ok(
        data={
            "agent_id": agent_id,
            "score": score.model_dump(mode="json"),
        },
    )


async def _collaboration_get_calibration(
    *,
    app_state: Any,  # noqa: ARG001
    arguments: dict[str, Any],  # noqa: ARG001
    actor: AgentIdentity | None = None,  # noqa: ARG001
) -> str:
    return capability_gap(
        "synthorg_collaboration_get_calibration",
        _WHY_COLLAB_CALIBRATION,
    )


AGENT_HANDLERS: Mapping[str, ToolHandler] = MappingProxyType(
    copy.deepcopy(
        {
            "synthorg_agents_list": _agents_list,
            "synthorg_agents_get": _agents_get,
            "synthorg_agents_create": _agents_create,
            "synthorg_agents_update": _agents_update,
            "synthorg_agents_delete": _agents_delete,
            "synthorg_agents_get_performance": _agents_get_performance,
            "synthorg_agents_get_activity": _agents_get_activity,
            "synthorg_agents_get_history": _agents_get_history,
            "synthorg_agents_get_health": _agents_get_health,
            "synthorg_personalities_list": _personalities_list,
            "synthorg_personalities_get": _personalities_get,
            "synthorg_training_list_sessions": _training_list_sessions,
            "synthorg_training_get_session": _training_get_session,
            "synthorg_training_start_session": _training_start_session,
            "synthorg_autonomy_get": _autonomy_get,
            "synthorg_autonomy_update": _autonomy_update,
            "synthorg_collaboration_get_score": _collaboration_get_score,
            "synthorg_collaboration_get_calibration": _collaboration_get_calibration,
        },
    ),
)
