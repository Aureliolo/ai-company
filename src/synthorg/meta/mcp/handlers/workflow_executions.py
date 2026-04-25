"""Workflow execution MCP handlers.

Split out of ``meta/mcp/handlers/workflows.py`` so the parent module
stays under the project's 800-line ceiling. The four execution handlers
(list / get / start / cancel) share the same envelope contract,
guardrails, and error mapping as the rest of the workflow domain --
they just have enough error branches that grouping them with the rest
pushed the parent module past budget.
"""

from typing import TYPE_CHECKING, Any

from synthorg.engine.errors import (
    SubworkflowDepthExceededError,
    WorkflowDefinitionInvalidError,
    WorkflowExecutionError,
    WorkflowExecutionNotFoundError,
)
from synthorg.engine.workflow.execution_service import (
    WorkflowExecutionService,  # noqa: TC001 -- runtime annotation in helper
)
from synthorg.meta.mcp.errors import (
    ArgumentValidationError,
    GuardrailViolationError,
    invalid_argument,
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
)

if TYPE_CHECKING:
    from synthorg.core.agent import AgentIdentity

logger = get_logger(__name__)


_TY_NON_BLANK = "non-blank string"
_ARG_DEF_ID = "workflow_id"
_ARG_EXEC_ID = "execution_id"
_WHY_EXECUTION_SERVICE = (
    "workflow_execution_service is not wired on app_state in this deployment"
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
    if actor is None:
        return None
    agent_id = getattr(actor, "id", None)
    if agent_id is not None:
        return str(agent_id)
    name = getattr(actor, "name", None)
    return name if isinstance(name, str) and name else None


def _require_non_blank(arguments: dict[str, Any], key: str) -> str:
    raw = arguments.get(key)
    if not isinstance(raw, str) or not raw.strip():
        raise invalid_argument(key, _TY_NON_BLANK)
    return raw.strip()


def _execution_service(app_state: Any) -> WorkflowExecutionService | None:
    return getattr(app_state, "workflow_execution_service", None)


def _parse_start_args(
    arguments: dict[str, Any],
) -> tuple[str, str, dict[str, Any]]:
    """Validate and extract args for ``synthorg_workflow_executions_start``.

    Extracted so :func:`workflow_executions_start` itself stays under the
    50-line ceiling -- the original inline parsing pushed it slightly
    over.
    """
    arg_project = "project"
    arg_context = "context"
    ty_object = "object"
    def_id = _require_non_blank(arguments, _ARG_DEF_ID)
    project_raw = arguments.get(arg_project) or "default"
    if not isinstance(project_raw, str) or not project_raw.strip():
        raise invalid_argument(arg_project, _TY_NON_BLANK)
    context_raw = arguments.get(arg_context, {})
    if not isinstance(context_raw, dict):
        raise invalid_argument(arg_context, ty_object)
    return def_id, project_raw.strip(), context_raw


async def workflow_executions_list(
    *,
    app_state: Any,
    arguments: dict[str, Any],
    actor: AgentIdentity | None = None,  # noqa: ARG001
) -> str:
    """List executions for a workflow definition."""
    tool = "synthorg_workflow_executions_list"
    service = _execution_service(app_state)
    if service is None:
        return capability_gap(tool, _WHY_EXECUTION_SERVICE)
    try:
        def_id = _require_non_blank(arguments, _ARG_DEF_ID)
        offset, limit = coerce_pagination(arguments)
    except ArgumentValidationError as exc:
        _log_invalid(tool, exc)
        return err(exc)
    try:
        executions = await service.list_executions(def_id)
        page, meta = paginate_sequence(executions, offset=offset, limit=limit)
    except MemoryError, RecursionError:
        raise
    except Exception as exc:
        _log_failed(tool, exc)
        return err(exc)
    logger.info(MCP_HANDLER_INVOKE_SUCCESS, tool_name=tool)
    return ok(data=dump_many(page), pagination=meta)


async def workflow_executions_get(
    *,
    app_state: Any,
    arguments: dict[str, Any],
    actor: AgentIdentity | None = None,  # noqa: ARG001
) -> str:
    """Fetch a single workflow execution by id."""
    tool = "synthorg_workflow_executions_get"
    service = _execution_service(app_state)
    if service is None:
        return capability_gap(tool, _WHY_EXECUTION_SERVICE)
    try:
        execution_id = _require_non_blank(arguments, _ARG_EXEC_ID)
    except ArgumentValidationError as exc:
        _log_invalid(tool, exc)
        return err(exc)
    try:
        execution = await service.get_execution(execution_id)
    except MemoryError, RecursionError:
        raise
    except Exception as exc:
        _log_failed(tool, exc)
        return err(exc)
    if execution is None:
        missing = WorkflowExecutionNotFoundError(
            f"Workflow execution {execution_id!r} not found",
        )
        _log_failed(tool, missing)
        return err(missing, domain_code="not_found")
    logger.info(MCP_HANDLER_INVOKE_SUCCESS, tool_name=tool)
    return ok(data=execution.model_dump(mode="json"))


async def workflow_executions_start(  # noqa: PLR0911 -- error mapping
    *,
    app_state: Any,
    arguments: dict[str, Any],
    actor: AgentIdentity | None = None,
) -> str:
    """Activate a workflow definition (alias: start an execution)."""
    tool = "synthorg_workflow_executions_start"
    service = _execution_service(app_state)
    if service is None:
        return capability_gap(tool, _WHY_EXECUTION_SERVICE)
    try:
        def_id, project, context_raw = _parse_start_args(arguments)
    except ArgumentValidationError as exc:
        _log_invalid(tool, exc)
        return err(exc)
    activated_by = _actor_id(actor) or "mcp"
    try:
        execution = await service.activate(
            def_id,
            project=project,
            activated_by=activated_by,
            context=context_raw,
        )
    except WorkflowExecutionNotFoundError as exc:
        _log_failed(tool, exc)
        return err(exc, domain_code="not_found")
    except (WorkflowDefinitionInvalidError, SubworkflowDepthExceededError) as exc:
        _log_failed(tool, exc)
        return err(exc, domain_code="invalid_argument")
    except WorkflowExecutionError as exc:
        _log_failed(tool, exc)
        return err(exc)
    except MemoryError, RecursionError:
        raise
    except Exception as exc:
        _log_failed(tool, exc)
        return err(exc)
    logger.info(MCP_HANDLER_INVOKE_SUCCESS, tool_name=tool)
    return ok(data=execution.model_dump(mode="json"))


async def workflow_executions_cancel(  # noqa: PLR0911 -- error mapping
    *,
    app_state: Any,
    arguments: dict[str, Any],
    actor: AgentIdentity | None = None,
) -> str:
    """Cancel a running workflow execution (destructive)."""
    tool = "synthorg_workflow_executions_cancel"
    try:
        execution_id = _require_non_blank(arguments, _ARG_EXEC_ID)
    except ArgumentValidationError as exc:
        _log_invalid(tool, exc)
        return err(exc)
    try:
        reason, resolved_actor = require_destructive_guardrails(arguments, actor)
    except GuardrailViolationError as exc:
        _log_guardrail(tool, exc)
        return err(exc)
    service = _execution_service(app_state)
    if service is None:
        return capability_gap(tool, _WHY_EXECUTION_SERVICE)
    cancelled_by = _actor_id(resolved_actor) or "mcp"
    try:
        execution = await service.cancel_execution(
            execution_id,
            cancelled_by=cancelled_by,
        )
    except WorkflowExecutionNotFoundError as exc:
        _log_failed(tool, exc)
        return err(exc, domain_code="not_found")
    except WorkflowExecutionError as exc:
        _log_failed(tool, exc)
        return err(exc, domain_code="conflict")
    except MemoryError, RecursionError:
        raise
    except Exception as exc:
        _log_failed(tool, exc)
        return err(exc)
    logger.info(MCP_HANDLER_INVOKE_SUCCESS, tool_name=tool)
    logger.info(
        MCP_DESTRUCTIVE_OP_EXECUTED,
        tool_name=tool,
        actor_agent_id=cancelled_by,
        reason=reason,
        target_id=execution_id,
    )
    return ok(data=execution.model_dump(mode="json"))


__all__ = [
    "workflow_executions_cancel",
    "workflow_executions_get",
    "workflow_executions_list",
    "workflow_executions_start",
]
