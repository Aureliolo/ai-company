"""Memory domain MCP handlers (fine-tune checkpoints + runs).

11 tools.  Reads (``list_checkpoints``, ``list_runs``) shim to
:class:`synthorg.memory.service.MemoryService` built per-call from
the persistence backend.  The fine-tune pipeline orchestration
methods (start/resume/cancel/run_preflight/deploy) require additional
state not exposed through a clean MCP arg set, so they return
``not_supported`` until a dedicated design pass lands.

Destructive ops: ``cancel_fine_tune``, ``rollback_checkpoint``, and
``delete_checkpoint`` all enforce the guardrail triple at the handler
boundary.  ``delete_checkpoint`` is live; the others are currently
``not_supported`` behind the guardrail.
"""

from types import MappingProxyType
from typing import TYPE_CHECKING, Any

from synthorg.memory.service import (
    CheckpointNotFoundError,
    MemoryService,
)
from synthorg.meta.mcp.errors import (
    ArgumentValidationError,
    GuardrailViolationError,
    invalid_argument,
)
from synthorg.meta.mcp.handlers.common import (
    PaginationMeta,
    dump_many,
    err,
    not_supported,
    ok,
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
from synthorg.persistence.errors import QueryError

if TYPE_CHECKING:
    from collections.abc import Mapping

    from synthorg.meta.mcp.invoker import ToolHandler

logger = get_logger(__name__)


_TY_NON_BLANK = "non-blank string"
_TY_NON_NEG_INT = "non-negative int"
_TY_POS_INT = "positive int"
_ARG_CHECKPOINT_ID = "checkpoint_id"
_ARG_OFFSET = "offset"
_ARG_LIMIT = "limit"


def _coerce_pagination(arguments: dict[str, Any]) -> tuple[int, int]:
    """Parse offset/limit as ints, raising ``ArgumentValidationError`` on bad input."""
    raw_offset: Any = arguments.get("offset")
    raw_limit: Any = arguments.get("limit")
    try:
        offset = 0 if raw_offset is None or raw_offset == "" else int(raw_offset)
    except (TypeError, ValueError) as exc:
        raise invalid_argument(_ARG_OFFSET, _TY_NON_NEG_INT) from exc
    try:
        limit = 50 if raw_limit is None or raw_limit == "" else int(raw_limit)
    except (TypeError, ValueError) as exc:
        raise invalid_argument(_ARG_LIMIT, _TY_POS_INT) from exc
    return offset, limit


def _log_invalid(tool: str, exc: Exception) -> None:
    logger.info(
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


def _actor_name(actor: Any) -> str | None:
    if actor is None:
        return None
    name = getattr(actor, "name", None)
    if isinstance(name, str) and name:
        return name
    agent_id = getattr(actor, "id", None)
    return str(agent_id) if agent_id is not None else None


def _require_non_blank(arguments: dict[str, Any], key: str) -> str:
    raw = arguments.get(key)
    if not isinstance(raw, str) or not raw.strip():
        raise invalid_argument(key, _TY_NON_BLANK)
    return raw


def _service(app_state: Any) -> MemoryService:
    """Build a per-call :class:`MemoryService`."""
    backend = app_state.persistence
    return MemoryService(
        checkpoint_repo=backend.fine_tune_checkpoints,
        run_repo=backend.fine_tune_runs,
        settings_service=(
            app_state.settings_service if app_state.has_settings_service else None
        ),
    )


_WHY_FINE_TUNE_START = (
    "fine-tune pipeline orchestration needs a TrainingPlan and a "
    "worker handle; no MCP-native schema exists yet"
)
_WHY_FINE_TUNE_PREFLIGHT = (
    "preflight validation runs inside the fine-tune controller; no "
    "standalone service method is exposed"
)
_WHY_RUNS = (
    "fine-tune run listing is served by the fine-tune controller; "
    "MemoryService does not expose a list method yet"
)
_WHY_EMBEDDER = (
    "active-embedder metadata is read from settings_service; no "
    "dedicated query method on MemoryService"
)


# --- handlers -------------------------------------------------------------


async def _memory_start_fine_tune(
    *,
    app_state: Any,  # noqa: ARG001
    arguments: dict[str, Any],  # noqa: ARG001
    actor: Any = None,  # noqa: ARG001
) -> str:
    return not_supported("synthorg_memory_start_fine_tune", _WHY_FINE_TUNE_START)


async def _memory_resume_fine_tune(
    *,
    app_state: Any,  # noqa: ARG001
    arguments: dict[str, Any],  # noqa: ARG001
    actor: Any = None,  # noqa: ARG001
) -> str:
    return not_supported("synthorg_memory_resume_fine_tune", _WHY_FINE_TUNE_START)


async def _memory_get_fine_tune_status(
    *,
    app_state: Any,  # noqa: ARG001
    arguments: dict[str, Any],  # noqa: ARG001
    actor: Any = None,  # noqa: ARG001
) -> str:
    return not_supported(
        "synthorg_memory_get_fine_tune_status",
        _WHY_RUNS,
    )


async def _memory_cancel_fine_tune(
    *,
    app_state: Any,  # noqa: ARG001
    arguments: dict[str, Any],
    actor: Any = None,
) -> str:
    tool = "synthorg_memory_cancel_fine_tune"
    try:
        require_destructive_guardrails(arguments, actor)
    except GuardrailViolationError as exc:
        _log_guardrail(tool, exc)
        return err(exc)
    return not_supported(tool, _WHY_FINE_TUNE_START)


async def _memory_run_preflight(
    *,
    app_state: Any,  # noqa: ARG001
    arguments: dict[str, Any],  # noqa: ARG001
    actor: Any = None,  # noqa: ARG001
) -> str:
    return not_supported(
        "synthorg_memory_run_preflight",
        _WHY_FINE_TUNE_PREFLIGHT,
    )


async def _memory_list_checkpoints(
    *,
    app_state: Any,
    arguments: dict[str, Any],
    actor: Any = None,  # noqa: ARG001
) -> str:
    tool = "synthorg_memory_list_checkpoints"
    try:
        offset, limit = _coerce_pagination(arguments)
    except ArgumentValidationError as exc:
        _log_invalid(tool, exc)
        return err(exc)
    try:
        checkpoints, total = await _service(app_state).list_checkpoints(
            limit=limit,
            offset=offset,
        )
    except Exception as exc:
        _log_failed(tool, exc)
        return err(exc)
    meta = PaginationMeta(total=total, offset=offset, limit=limit)
    logger.debug(MCP_HANDLER_INVOKE_SUCCESS, tool_name=tool)
    return ok(data=dump_many(checkpoints), pagination=meta)


async def _memory_deploy_checkpoint(
    *,
    app_state: Any,
    arguments: dict[str, Any],
    actor: Any = None,  # noqa: ARG001
) -> str:
    tool = "synthorg_memory_deploy_checkpoint"
    try:
        checkpoint_id = _require_non_blank(arguments, _ARG_CHECKPOINT_ID)
    except ArgumentValidationError as exc:
        _log_invalid(tool, exc)
        return err(exc)
    try:
        cp = await _service(app_state).deploy_checkpoint(checkpoint_id)
    except CheckpointNotFoundError as exc:
        _log_failed(tool, exc)
        return err(exc, domain_code="not_found")
    except Exception as exc:
        _log_failed(tool, exc)
        return err(exc)
    logger.debug(MCP_HANDLER_INVOKE_SUCCESS, tool_name=tool)
    return ok(data=cp.model_dump(mode="json"))


async def _memory_rollback_checkpoint(
    *,
    app_state: Any,  # noqa: ARG001
    arguments: dict[str, Any],
    actor: Any = None,
) -> str:
    tool = "synthorg_memory_rollback_checkpoint"
    try:
        require_destructive_guardrails(arguments, actor)
    except GuardrailViolationError as exc:
        _log_guardrail(tool, exc)
        return err(exc)
    return not_supported(
        tool,
        "rollback requires prior-active capture; only the fine-tune "
        "controller has access to that context today",
    )


async def _memory_delete_checkpoint(
    *,
    app_state: Any,
    arguments: dict[str, Any],
    actor: Any = None,
) -> str:
    tool = "synthorg_memory_delete_checkpoint"
    try:
        checkpoint_id = _require_non_blank(arguments, _ARG_CHECKPOINT_ID)
    except ArgumentValidationError as exc:
        _log_invalid(tool, exc)
        return err(exc)
    try:
        reason, _ = require_destructive_guardrails(arguments, actor)
    except GuardrailViolationError as exc:
        _log_guardrail(tool, exc)
        return err(exc)

    try:
        await _service(app_state).delete_checkpoint(checkpoint_id)
    except CheckpointNotFoundError as exc:
        _log_failed(tool, exc)
        return err(exc, domain_code="not_found")
    except QueryError as exc:
        # Active-checkpoint / domain-rule violation -- surface as
        # ``conflict`` so callers can distinguish from internal errors.
        _log_failed(tool, exc)
        return err(exc, domain_code="conflict")
    except Exception as exc:
        _log_failed(tool, exc)
        return err(exc)

    logger.info(
        MCP_DESTRUCTIVE_OP_EXECUTED,
        tool_name=tool,
        actor_agent_id=_actor_name(actor),
        reason=reason,
        target_id=checkpoint_id,
    )
    return ok()


async def _memory_list_runs(
    *,
    app_state: Any,  # noqa: ARG001
    arguments: dict[str, Any],  # noqa: ARG001
    actor: Any = None,  # noqa: ARG001
) -> str:
    return not_supported("synthorg_memory_list_runs", _WHY_RUNS)


async def _memory_get_active_embedder(
    *,
    app_state: Any,  # noqa: ARG001
    arguments: dict[str, Any],  # noqa: ARG001
    actor: Any = None,  # noqa: ARG001
) -> str:
    return not_supported("synthorg_memory_get_active_embedder", _WHY_EMBEDDER)


MEMORY_HANDLERS: Mapping[str, ToolHandler] = MappingProxyType(
    {
        "synthorg_memory_start_fine_tune": _memory_start_fine_tune,
        "synthorg_memory_resume_fine_tune": _memory_resume_fine_tune,
        "synthorg_memory_get_fine_tune_status": _memory_get_fine_tune_status,
        "synthorg_memory_cancel_fine_tune": _memory_cancel_fine_tune,
        "synthorg_memory_run_preflight": _memory_run_preflight,
        "synthorg_memory_list_checkpoints": _memory_list_checkpoints,
        "synthorg_memory_deploy_checkpoint": _memory_deploy_checkpoint,
        "synthorg_memory_rollback_checkpoint": _memory_rollback_checkpoint,
        "synthorg_memory_delete_checkpoint": _memory_delete_checkpoint,
        "synthorg_memory_list_runs": _memory_list_runs,
        "synthorg_memory_get_active_embedder": _memory_get_active_embedder,
    },
)
