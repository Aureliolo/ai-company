"""Task domain MCP handlers.

Shims the 8 task tools onto ``app_state.task_engine``
(:class:`synthorg.engine.task_engine.TaskEngine`).  ``delete`` and
``cancel`` are destructive and enforce the standard
``confirm=True`` + non-blank ``reason`` + non-``None`` ``actor`` triple.
``activities_list`` has no dedicated service method; it returns a
``capability_gap`` envelope.
"""

import copy
from collections.abc import Mapping  # noqa: TC003 -- PEP 649 annotation
from types import MappingProxyType
from typing import TYPE_CHECKING, Any

from pydantic import ValidationError

from synthorg.core.enums import TaskStatus
from synthorg.engine.errors import (
    TaskMutationError,
    TaskNotFoundError,
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
    PaginationMeta,
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

logger = get_logger(__name__)


_TY_NON_BLANK = "non-blank string"
_TY_AGENT = "identified agent"
_TY_TASK_STATUS = "TaskStatus"
_ARG_TASK_ID = "task_id"
_ARG_TARGET = "target_status"
_ARG_UPDATES = "updates"
_ARG_STATUS = "status"
_ARG_ASSIGNED_TO = "assigned_to"
_ARG_PROJECT = "project"
_ARG_ACTOR = "actor"


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
    raw = require_arg(arguments, key, str)
    if not raw.strip():
        raise invalid_argument(key, _TY_NON_BLANK)
    return raw.strip()


def _coerce_status(
    raw: Any,
    *,
    arg_name: str = _ARG_STATUS,
) -> TaskStatus | None:
    """Coerce a string to ``TaskStatus`` or raise ``ArgumentValidationError``.

    ``arg_name`` controls which argument the envelope blames so callers
    parsing ``status`` vs ``target_status`` get accurate feedback
    instead of every validation failure pointing at ``"status"``.
    """
    if raw is None:
        return None
    if not isinstance(raw, str):
        raise invalid_argument(arg_name, _TY_NON_BLANK)
    try:
        return TaskStatus(raw)
    except ValueError as exc:
        raise invalid_argument(arg_name, _TY_TASK_STATUS) from exc


# --- handlers -------------------------------------------------------------


async def _tasks_list(
    *,
    app_state: Any,
    arguments: dict[str, Any],
    actor: AgentIdentity | None = None,  # noqa: ARG001
) -> str:
    tool = "synthorg_tasks_list"
    try:
        status = _coerce_status(arguments.get("status"))
        assigned_to = arguments.get("assigned_to")
        project = arguments.get("project")
        if assigned_to is not None and not isinstance(assigned_to, str):
            raise invalid_argument(_ARG_ASSIGNED_TO, _TY_NON_BLANK)
        if project is not None and not isinstance(project, str):
            raise invalid_argument(_ARG_PROJECT, _TY_NON_BLANK)
        offset, limit = coerce_pagination(arguments)
    except ArgumentValidationError as exc:
        _log_invalid(tool, exc)
        return err(exc)

    try:
        tasks, total = await app_state.task_engine.list_tasks(
            status=status,
            assigned_to=assigned_to,
            project=project,
        )
        page, meta = paginate_sequence(
            tasks,
            offset=offset,
            limit=limit,
            total=total,
        )
    except Exception as exc:
        _log_failed(tool, exc)
        return err(exc)
    logger.info(MCP_HANDLER_INVOKE_SUCCESS, tool_name=tool)
    return ok(data=dump_many(page), pagination=meta)


async def _tasks_get(
    *,
    app_state: Any,
    arguments: dict[str, Any],
    actor: AgentIdentity | None = None,  # noqa: ARG001
) -> str:
    tool = "synthorg_tasks_get"
    try:
        task_id = _require_non_blank(arguments, _ARG_TASK_ID)
    except ArgumentValidationError as exc:
        _log_invalid(tool, exc)
        return err(exc)
    try:
        task = await app_state.task_engine.get_task(task_id)
    except Exception as exc:
        _log_failed(tool, exc)
        return err(exc)
    if task is None:
        missing = TaskNotFoundError(f"Task {task_id!r} not found")
        _log_failed(tool, missing)
        return err(missing, domain_code="not_found")
    logger.info(MCP_HANDLER_INVOKE_SUCCESS, tool_name=tool)
    return ok(data=task.model_dump(mode="json"))


async def _tasks_create(
    *,
    app_state: Any,
    arguments: dict[str, Any],
    actor: AgentIdentity | None = None,
) -> str:
    tool = "synthorg_tasks_create"
    try:
        task_data = require_arg(arguments, "task_data", dict)
    except ArgumentValidationError as exc:
        _log_invalid(tool, exc)
        return err(exc)

    # Validate full CreateTaskData via Pydantic so callers get a precise
    # error envelope instead of a runtime TaskMutationError on missing
    # / mistyped fields.  Local import keeps the meta handlers from
    # eagerly pulling the engine module on every import.
    from synthorg.engine.task_engine_models import (  # noqa: PLC0415
        CreateTaskData,
    )

    try:
        data = CreateTaskData.model_validate(task_data)
    except ValidationError as exc:
        _log_invalid(tool, exc)
        return err(exc, domain_code="invalid_argument")

    requested_by = _actor_id(actor) or "system"
    try:
        task = await app_state.task_engine.create_task(
            data,
            requested_by=requested_by,
        )
    except TaskMutationError as exc:
        _log_failed(tool, exc)
        return err(exc)
    except MemoryError, RecursionError:
        raise
    except Exception as exc:
        _log_failed(tool, exc)
        return err(exc)
    logger.info(MCP_HANDLER_INVOKE_SUCCESS, tool_name=tool)
    return ok(data=task.model_dump(mode="json"))


async def _tasks_update(
    *,
    app_state: Any,
    arguments: dict[str, Any],
    actor: AgentIdentity | None = None,
) -> str:
    tool = "synthorg_tasks_update"
    try:
        requested_by = _actor_id(actor)
        if requested_by is None:
            raise invalid_argument(_ARG_ACTOR, _TY_AGENT)
        task_id = _require_non_blank(arguments, _ARG_TASK_ID)
        updates = require_arg(arguments, _ARG_UPDATES, dict)
    except ArgumentValidationError as exc:
        _log_invalid(tool, exc)
        return err(exc)

    try:
        task = await app_state.task_engine.update_task(
            task_id,
            updates,
            requested_by=requested_by,
        )
    except TaskNotFoundError as exc:
        _log_failed(tool, exc)
        return err(exc, domain_code="not_found")
    except TaskMutationError as exc:
        _log_failed(tool, exc)
        return err(exc)
    except Exception as exc:
        _log_failed(tool, exc)
        return err(exc)
    logger.info(MCP_HANDLER_INVOKE_SUCCESS, tool_name=tool)
    return ok(data=task.model_dump(mode="json"))


async def _tasks_delete(
    *,
    app_state: Any,
    arguments: dict[str, Any],
    actor: AgentIdentity | None = None,
) -> str:
    tool = "synthorg_tasks_delete"
    try:
        task_id = _require_non_blank(arguments, _ARG_TASK_ID)
    except ArgumentValidationError as exc:
        _log_invalid(tool, exc)
        return err(exc)
    try:
        reason, _ = require_destructive_guardrails(arguments, actor)
    except GuardrailViolationError as exc:
        _log_guardrail(tool, exc)
        return err(exc)

    requested_by = _actor_id(actor) or "system"
    try:
        await app_state.task_engine.delete_task(
            task_id,
            requested_by=requested_by,
        )
    except TaskNotFoundError as exc:
        _log_failed(tool, exc)
        return err(exc, domain_code="not_found")
    except TaskMutationError as exc:
        _log_failed(tool, exc)
        return err(exc)
    except Exception as exc:
        _log_failed(tool, exc)
        return err(exc)

    logger.info(MCP_HANDLER_INVOKE_SUCCESS, tool_name=tool)
    logger.info(
        MCP_DESTRUCTIVE_OP_EXECUTED,
        tool_name=tool,
        actor_agent_id=requested_by,
        reason=reason,
        target_id=task_id,
    )
    return ok()


async def _tasks_transition(
    *,
    app_state: Any,
    arguments: dict[str, Any],
    actor: AgentIdentity | None = None,
) -> str:
    tool = "synthorg_tasks_transition"
    try:
        requested_by = _actor_id(actor)
        if requested_by is None:
            raise invalid_argument(_ARG_ACTOR, _TY_AGENT)
        task_id = _require_non_blank(arguments, _ARG_TASK_ID)
        target_raw = _require_non_blank(arguments, _ARG_TARGET)
        target = _coerce_status(target_raw, arg_name=_ARG_TARGET)
        if target is None:
            raise invalid_argument(_ARG_TARGET, _TY_TASK_STATUS)
    except ArgumentValidationError as exc:
        _log_invalid(tool, exc)
        return err(exc)

    try:
        task, _previous = await app_state.task_engine.transition_task(
            task_id,
            target,
            requested_by=requested_by,
        )
    except TaskNotFoundError as exc:
        _log_failed(tool, exc)
        return err(exc, domain_code="not_found")
    except TaskMutationError as exc:
        _log_failed(tool, exc)
        return err(exc)
    except Exception as exc:
        _log_failed(tool, exc)
        return err(exc)
    logger.info(MCP_HANDLER_INVOKE_SUCCESS, tool_name=tool)
    return ok(data=task.model_dump(mode="json"))


async def _tasks_cancel(
    *,
    app_state: Any,
    arguments: dict[str, Any],
    actor: AgentIdentity | None = None,
) -> str:
    tool = "synthorg_tasks_cancel"
    try:
        task_id = _require_non_blank(arguments, _ARG_TASK_ID)
    except ArgumentValidationError as exc:
        _log_invalid(tool, exc)
        return err(exc)
    try:
        reason, _ = require_destructive_guardrails(arguments, actor)
    except GuardrailViolationError as exc:
        _log_guardrail(tool, exc)
        return err(exc)

    requested_by = _actor_id(actor) or "system"
    try:
        task = await app_state.task_engine.cancel_task(
            task_id,
            requested_by=requested_by,
            reason=reason,
        )
    except TaskNotFoundError as exc:
        _log_failed(tool, exc)
        return err(exc, domain_code="not_found")
    except TaskMutationError as exc:
        _log_failed(tool, exc)
        return err(exc)
    except Exception as exc:
        _log_failed(tool, exc)
        return err(exc)

    logger.info(MCP_HANDLER_INVOKE_SUCCESS, tool_name=tool)
    logger.info(
        MCP_DESTRUCTIVE_OP_EXECUTED,
        tool_name=tool,
        actor_agent_id=requested_by,
        reason=reason,
        target_id=task_id,
    )
    return ok(data=task.model_dump(mode="json"))


_WHY_ACTIVITY = (
    "activity feed is assembled in hr.activity module but the "
    "ActivityFeedService is not wired on app_state in this deployment"
)


async def _activities_list(
    *,
    app_state: Any,
    arguments: dict[str, Any],
    actor: AgentIdentity | None = None,  # noqa: ARG001
) -> str:
    tool = "synthorg_activities_list"
    arg_project = "project"
    arg_task_id = "task_id"
    try:
        offset, limit = coerce_pagination(arguments)
        project_raw = arguments.get(arg_project)
        task_id_raw = arguments.get(arg_task_id)
        if project_raw is not None and (
            not isinstance(project_raw, str) or not project_raw.strip()
        ):
            raise invalid_argument(arg_project, _TY_NON_BLANK)
        if task_id_raw is not None and (
            not isinstance(task_id_raw, str) or not task_id_raw.strip()
        ):
            raise invalid_argument(arg_task_id, _TY_NON_BLANK)
    except ArgumentValidationError as exc:
        _log_invalid(tool, exc)
        return err(exc)
    if not getattr(app_state, "has_activity_feed_service", False):
        return capability_gap(tool, _WHY_ACTIVITY)
    try:
        events, total = await app_state.activity_feed_service.list_recent_activity(
            project=project_raw.strip() if project_raw is not None else None,
            task_id=task_id_raw.strip() if task_id_raw is not None else None,
            offset=offset,
            limit=limit,
        )
    except MemoryError, RecursionError:
        raise
    except Exception as exc:
        _log_failed(tool, exc)
        return err(exc)
    meta = PaginationMeta(total=total, offset=offset, limit=limit)
    logger.info(MCP_HANDLER_INVOKE_SUCCESS, tool_name=tool)
    return ok(data=dump_many(events), pagination=meta)


TASK_HANDLERS: Mapping[str, ToolHandler] = MappingProxyType(
    copy.deepcopy(
        {
            "synthorg_tasks_list": _tasks_list,
            "synthorg_tasks_get": _tasks_get,
            "synthorg_tasks_create": _tasks_create,
            "synthorg_tasks_update": _tasks_update,
            "synthorg_tasks_delete": _tasks_delete,
            "synthorg_tasks_transition": _tasks_transition,
            "synthorg_tasks_cancel": _tasks_cancel,
            "synthorg_activities_list": _activities_list,
        },
    ),
)
