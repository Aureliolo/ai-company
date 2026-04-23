"""Workflow domain MCP handlers.

16 tools spanning workflow definitions, subworkflows, executions, and
versions.  Reads on the core definitions shim to
:class:`synthorg.engine.workflow.service.WorkflowService` via the
persistence repos on ``app_state.persistence``.  Subworkflows,
executions, and versions do not currently have an orchestration
service exposed on ``app_state``; they return ``capability_gap`` so the
tool stays registered and visible to ops until a dedicated service
lands.

Destructive ops: ``workflows_delete``, ``subworkflows_delete``, and
``workflow_executions_cancel`` all require the full destructive-op
guardrail.  ``workflows_delete`` is live; the other two return
``capability_gap`` for now but still enforce the guardrail at the
schema layer.
"""

import copy
from collections.abc import Mapping  # noqa: TC003 -- PEP 649 annotation
from types import MappingProxyType
from typing import TYPE_CHECKING, Any

from synthorg.engine.workflow.service import (
    WorkflowDefinitionNotFoundError,
    WorkflowService,
)
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
    require_destructive_guardrails,
)
from synthorg.observability import get_logger, safe_error_description
from synthorg.observability.events.mcp import (
    MCP_DESTRUCTIVE_OP_EXECUTED,
    MCP_HANDLER_ARGUMENT_INVALID,
    MCP_HANDLER_GUARDRAIL_VIOLATED,
    MCP_HANDLER_INVOKE_FAILED,
    MCP_HANDLER_INVOKE_SUCCESS,
    MCP_HANDLER_LAZY_SERVICE_INIT,
)

if TYPE_CHECKING:
    from synthorg.core.agent import AgentIdentity

logger = get_logger(__name__)


_TY_NON_BLANK = "non-blank string"
_ARG_DEF_ID = "workflow_id"


_WHY_SUBWORKFLOWS = (
    "subworkflow repository is reached via the subworkflows controller; "
    "no service facade is attached to app_state"
)
_WHY_EXECUTIONS = (
    "workflow execution orchestration lives behind the engine loop; "
    "no execution store is attached to app_state"
)
_WHY_VERSIONS_LIST = (
    "workflow version snapshots are reached via workflow_versions "
    "controller; no service is attached to app_state"
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
    """Return a stable audit identifier for ``actor`` (prefers ``.id``)."""
    if actor is None:
        return None
    agent_id = getattr(actor, "id", None)
    if agent_id is not None:
        return str(agent_id)
    name = getattr(actor, "name", None)
    return name if isinstance(name, str) and name else None


def _require_non_blank(arguments: dict[str, Any], key: str) -> str:
    """Extract a non-blank string argument, stripped of surrounding whitespace."""
    raw = arguments.get(key)
    if not isinstance(raw, str) or not raw.strip():
        raise invalid_argument(key, _TY_NON_BLANK)
    return raw.strip()


def _service(app_state: Any) -> WorkflowService:
    """Return the workflow service facade.

    Prefers ``app_state.workflow_service`` when bootstrap has wired one
    (keeps handlers off ``persistence.*``).  Falls back to per-call
    construction from the persistence backend for app_states that have
    not adopted the cached-service pattern yet; the fallback path emits
    a DEBUG log so deployments using the legacy wiring are observable
    in telemetry.
    """
    cached: WorkflowService | None = getattr(app_state, "workflow_service", None)
    if cached is not None:
        return cached
    logger.debug(
        MCP_HANDLER_LAZY_SERVICE_INIT,
        tool_name="workflows._service",
        service="workflow_service",
        reason="app_state.workflow_service not wired -- building per-call",
    )
    return WorkflowService(
        definition_repo=app_state.persistence.workflow_definitions,
        version_repo=app_state.persistence.workflow_versions,
    )


# --- workflow definition CRUD ---------------------------------------------


async def _workflows_list(
    *,
    app_state: Any,
    arguments: dict[str, Any],
    actor: AgentIdentity | None = None,  # noqa: ARG001
) -> str:
    tool = "synthorg_workflows_list"
    try:
        offset, limit = coerce_pagination(arguments)
    except ArgumentValidationError as exc:
        _log_invalid(tool, exc)
        return err(exc)
    try:
        items = await _service(app_state).list_definitions()
        page, meta = paginate_sequence(items, offset=offset, limit=limit)
    except MemoryError, RecursionError:
        raise
    except Exception as exc:
        _log_failed(tool, exc)
        return err(exc)
    logger.info(MCP_HANDLER_INVOKE_SUCCESS, tool_name=tool)
    return ok(data=dump_many(page), pagination=meta)


async def _workflows_get(
    *,
    app_state: Any,
    arguments: dict[str, Any],
    actor: AgentIdentity | None = None,  # noqa: ARG001
) -> str:
    tool = "synthorg_workflows_get"
    try:
        def_id = _require_non_blank(arguments, _ARG_DEF_ID)
    except ArgumentValidationError as exc:
        _log_invalid(tool, exc)
        return err(exc)
    try:
        defn = await _service(app_state).get_definition(def_id)
    except MemoryError, RecursionError:
        raise
    except Exception as exc:
        _log_failed(tool, exc)
        return err(exc)
    if defn is None:
        missing = WorkflowDefinitionNotFoundError(
            f"Workflow definition {def_id!r} not found",
        )
        _log_failed(tool, missing)
        return err(missing, domain_code="not_found")
    logger.info(MCP_HANDLER_INVOKE_SUCCESS, tool_name=tool)
    return ok(data=defn.model_dump(mode="json"))


async def _workflows_create(
    *,
    app_state: Any,  # noqa: ARG001
    arguments: dict[str, Any],  # noqa: ARG001
    actor: AgentIdentity | None = None,  # noqa: ARG001
) -> str:
    return capability_gap(
        "synthorg_workflows_create",
        "workflow definition creation requires the full "
        "WorkflowDefinition schema; use the REST API",
    )


async def _workflows_update(
    *,
    app_state: Any,  # noqa: ARG001
    arguments: dict[str, Any],  # noqa: ARG001
    actor: AgentIdentity | None = None,  # noqa: ARG001
) -> str:
    return capability_gap(
        "synthorg_workflows_update",
        "workflow definition updates need the full WorkflowDefinition "
        "with optimistic-concurrency revision; use the REST API",
    )


async def _workflows_delete(
    *,
    app_state: Any,
    arguments: dict[str, Any],
    actor: AgentIdentity | None = None,
) -> str:
    tool = "synthorg_workflows_delete"
    try:
        def_id = _require_non_blank(arguments, _ARG_DEF_ID)
    except ArgumentValidationError as exc:
        _log_invalid(tool, exc)
        return err(exc)
    try:
        reason, _ = require_destructive_guardrails(arguments, actor)
    except GuardrailViolationError as exc:
        _log_guardrail(tool, exc)
        return err(exc)

    try:
        deleted = await _service(app_state).delete_definition(def_id)
    except MemoryError, RecursionError:
        raise
    except Exception as exc:
        _log_failed(tool, exc)
        return err(exc)
    if not deleted:
        missing = WorkflowDefinitionNotFoundError(
            f"Workflow definition {def_id!r} not found",
        )
        _log_failed(tool, missing)
        return err(missing, domain_code="not_found")

    logger.info(MCP_HANDLER_INVOKE_SUCCESS, tool_name=tool)
    logger.info(
        MCP_DESTRUCTIVE_OP_EXECUTED,
        tool_name=tool,
        actor_agent_id=_actor_id(actor),
        reason=reason,
        target_id=def_id,
    )
    return ok()


async def _workflows_validate(
    *,
    app_state: Any,  # noqa: ARG001
    arguments: dict[str, Any],  # noqa: ARG001
    actor: AgentIdentity | None = None,  # noqa: ARG001
) -> str:
    return capability_gap(
        "synthorg_workflows_validate",
        "workflow validation runs inside the validation middleware; "
        "no standalone validator is exposed on app_state",
    )


# --- subworkflows ---------------------------------------------------------


async def _subworkflow_placeholder(tool_name: str) -> str:
    return capability_gap(tool_name, _WHY_SUBWORKFLOWS)


async def _subworkflows_list(
    *,
    app_state: Any,  # noqa: ARG001
    arguments: dict[str, Any],  # noqa: ARG001
    actor: AgentIdentity | None = None,  # noqa: ARG001
) -> str:
    return await _subworkflow_placeholder("synthorg_subworkflows_list")


async def _subworkflows_get(
    *,
    app_state: Any,  # noqa: ARG001
    arguments: dict[str, Any],  # noqa: ARG001
    actor: AgentIdentity | None = None,  # noqa: ARG001
) -> str:
    return await _subworkflow_placeholder("synthorg_subworkflows_get")


async def _subworkflows_create(
    *,
    app_state: Any,  # noqa: ARG001
    arguments: dict[str, Any],  # noqa: ARG001
    actor: AgentIdentity | None = None,  # noqa: ARG001
) -> str:
    return await _subworkflow_placeholder("synthorg_subworkflows_create")


async def _subworkflows_delete(
    *,
    app_state: Any,  # noqa: ARG001
    arguments: dict[str, Any],
    actor: AgentIdentity | None = None,
) -> str:
    tool = "synthorg_subworkflows_delete"
    try:
        require_destructive_guardrails(arguments, actor)
    except GuardrailViolationError as exc:
        _log_guardrail(tool, exc)
        return err(exc)
    return capability_gap(tool, _WHY_SUBWORKFLOWS)


# --- workflow executions --------------------------------------------------


async def _executions_placeholder(tool_name: str) -> str:
    return capability_gap(tool_name, _WHY_EXECUTIONS)


async def _workflow_executions_list(
    *,
    app_state: Any,  # noqa: ARG001
    arguments: dict[str, Any],  # noqa: ARG001
    actor: AgentIdentity | None = None,  # noqa: ARG001
) -> str:
    return await _executions_placeholder("synthorg_workflow_executions_list")


async def _workflow_executions_get(
    *,
    app_state: Any,  # noqa: ARG001
    arguments: dict[str, Any],  # noqa: ARG001
    actor: AgentIdentity | None = None,  # noqa: ARG001
) -> str:
    return await _executions_placeholder("synthorg_workflow_executions_get")


async def _workflow_executions_start(
    *,
    app_state: Any,  # noqa: ARG001
    arguments: dict[str, Any],  # noqa: ARG001
    actor: AgentIdentity | None = None,  # noqa: ARG001
) -> str:
    return await _executions_placeholder("synthorg_workflow_executions_start")


async def _workflow_executions_cancel(
    *,
    app_state: Any,  # noqa: ARG001
    arguments: dict[str, Any],
    actor: AgentIdentity | None = None,
) -> str:
    tool = "synthorg_workflow_executions_cancel"
    try:
        require_destructive_guardrails(arguments, actor)
    except GuardrailViolationError as exc:
        _log_guardrail(tool, exc)
        return err(exc)
    return capability_gap(tool, _WHY_EXECUTIONS)


# --- workflow version history --------------------------------------------


async def _workflow_versions_list(
    *,
    app_state: Any,  # noqa: ARG001
    arguments: dict[str, Any],  # noqa: ARG001
    actor: AgentIdentity | None = None,  # noqa: ARG001
) -> str:
    return capability_gap("synthorg_workflow_versions_list", _WHY_VERSIONS_LIST)


async def _workflow_versions_get(
    *,
    app_state: Any,  # noqa: ARG001
    arguments: dict[str, Any],  # noqa: ARG001
    actor: AgentIdentity | None = None,  # noqa: ARG001
) -> str:
    return capability_gap("synthorg_workflow_versions_get", _WHY_VERSIONS_LIST)


WORKFLOW_HANDLERS: Mapping[str, ToolHandler] = MappingProxyType(
    copy.deepcopy(
        {
            "synthorg_workflows_list": _workflows_list,
            "synthorg_workflows_get": _workflows_get,
            "synthorg_workflows_create": _workflows_create,
            "synthorg_workflows_update": _workflows_update,
            "synthorg_workflows_delete": _workflows_delete,
            "synthorg_workflows_validate": _workflows_validate,
            "synthorg_subworkflows_list": _subworkflows_list,
            "synthorg_subworkflows_get": _subworkflows_get,
            "synthorg_subworkflows_create": _subworkflows_create,
            "synthorg_subworkflows_delete": _subworkflows_delete,
            "synthorg_workflow_executions_list": _workflow_executions_list,
            "synthorg_workflow_executions_get": _workflow_executions_get,
            "synthorg_workflow_executions_start": _workflow_executions_start,
            "synthorg_workflow_executions_cancel": _workflow_executions_cancel,
            "synthorg_workflow_versions_list": _workflow_versions_list,
            "synthorg_workflow_versions_get": _workflow_versions_get,
        },
    ),
)
