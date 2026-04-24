"""Memory domain MCP handlers (fine-tune checkpoints + runs).

11 tools, all wired through :class:`MemoryService` after META-MCP-4.
The service is injected via ``app_state.memory_service`` when the
application bootstrap has wired one; otherwise a per-call service is
built from the persistence backend (``fine_tune_checkpoints`` +
``fine_tune_runs``) with a ``None`` orchestrator slot. Any attempt to
invoke a fine-tune lifecycle method on a service without an
orchestrator raises :class:`BackendUnsupportedError`, which handlers
catch and surface via :func:`not_supported` (the ``not_supported``
wire envelope plus :data:`MCP_HANDLER_NOT_IMPLEMENTED`).

Destructive ops: ``cancel_fine_tune``, ``rollback_checkpoint``, and
``delete_checkpoint`` enforce the guardrail triple at the handler
boundary and emit :data:`MCP_DESTRUCTIVE_OP_EXECUTED` on success.
"""

import copy
from collections.abc import Mapping  # noqa: TC003 -- PEP 649 annotation
from types import MappingProxyType
from typing import TYPE_CHECKING, Any

from synthorg.core.types import NotBlankStr
from synthorg.memory.fine_tune_plan import (
    BackendUnsupportedError,
    FineTunePlan,
)
from synthorg.memory.service import (
    CheckpointNotFoundError,
    CheckpointRollbackCorruptError,
    CheckpointRollbackUnavailableError,
    MemoryService,
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
    coerce_pagination,
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
    from synthorg.core.agent import AgentIdentity

logger = get_logger(__name__)


_TY_NON_BLANK = "non-blank string"
_ARG_CHECKPOINT_ID = "checkpoint_id"
_ARG_RUN_ID = "run_id"


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


def _service(app_state: Any) -> MemoryService:
    """Return the :class:`MemoryService` facade.

    Prefers ``app_state.memory_service`` when bootstrap has wired one
    (keeps handlers off ``persistence.*``). Falls back to per-call
    construction from the persistence backend for app_states that have
    not adopted the cached-service pattern yet. Accessor calls that
    hit an unsupported backend (e.g. Postgres, which does not yet
    expose ``fine_tune_checkpoints``) raise
    :class:`BackendUnsupportedError` so the calling handler can return
    a clean ``not_supported`` envelope.

    Raises:
        BackendUnsupportedError: If the backend does not implement
            the fine-tune repositories.
    """
    if getattr(app_state, "has_memory_service", False):
        attached: MemoryService = app_state.memory_service
        return attached
    cached: MemoryService | None = getattr(app_state, "memory_service", None)
    if cached is not None:
        return cached
    backend = app_state.persistence
    try:
        checkpoint_repo = backend.fine_tune_checkpoints
        run_repo = backend.fine_tune_runs
    except NotImplementedError as exc:
        raise BackendUnsupportedError(_WHY_BACKEND_NO_FINE_TUNE) from exc
    has_settings = getattr(app_state, "has_settings_service", False)
    return MemoryService(
        checkpoint_repo=checkpoint_repo,
        run_repo=run_repo,
        settings_service=(
            getattr(app_state, "settings_service", None) if has_settings else None
        ),
        orchestrator=getattr(app_state, "_fine_tune_orchestrator", None),
    )


_WHY_BACKEND_NO_FINE_TUNE = (
    "fine-tune repositories are not supported by the active "
    "persistence backend (SQLite-only today); switch backends or use "
    "the fine-tune controller"
)


# --- handlers -------------------------------------------------------------


async def _memory_start_fine_tune(
    *,
    app_state: Any,
    arguments: dict[str, Any],
    actor: AgentIdentity | None = None,  # noqa: ARG001
) -> str:
    tool = "synthorg_memory_start_fine_tune"
    try:
        plan = _parse_fine_tune_plan(arguments)
    except ArgumentValidationError as exc:
        _log_invalid(tool, exc)
        return err(exc)
    try:
        service = _service(app_state)
        run = await service.start_fine_tune(plan)
    except BackendUnsupportedError as exc:
        return not_supported(tool, str(exc))
    except Exception as exc:
        _log_failed(tool, exc)
        return err(exc)
    logger.info(MCP_HANDLER_INVOKE_SUCCESS, tool_name=tool)
    return ok(data=run.model_dump(mode="json"))


async def _memory_resume_fine_tune(
    *,
    app_state: Any,
    arguments: dict[str, Any],
    actor: AgentIdentity | None = None,  # noqa: ARG001
) -> str:
    tool = "synthorg_memory_resume_fine_tune"
    try:
        run_id = _require_non_blank(arguments, _ARG_RUN_ID)
    except ArgumentValidationError as exc:
        _log_invalid(tool, exc)
        return err(exc)
    try:
        service = _service(app_state)
        run = await service.resume_fine_tune(NotBlankStr(run_id))
    except BackendUnsupportedError as exc:
        return not_supported(tool, str(exc))
    except ValueError as exc:
        _log_failed(tool, exc)
        return err(exc, domain_code="not_found")
    except Exception as exc:
        _log_failed(tool, exc)
        return err(exc)
    logger.info(MCP_HANDLER_INVOKE_SUCCESS, tool_name=tool)
    return ok(data=run.model_dump(mode="json"))


async def _memory_get_fine_tune_status(
    *,
    app_state: Any,
    arguments: dict[str, Any],
    actor: AgentIdentity | None = None,  # noqa: ARG001
) -> str:
    tool = "synthorg_memory_get_fine_tune_status"
    run_id_raw = arguments.get(_ARG_RUN_ID)
    run_id: NotBlankStr | None = None
    if run_id_raw is not None:
        if not isinstance(run_id_raw, str) or not run_id_raw.strip():
            exc = invalid_argument(_ARG_RUN_ID, _TY_NON_BLANK)
            _log_invalid(tool, exc)
            return err(exc)
        run_id = NotBlankStr(run_id_raw.strip())
    try:
        service = _service(app_state)
        status = await service.get_fine_tune_status(run_id)
    except BackendUnsupportedError as exc:
        return not_supported(tool, str(exc))
    except ValueError as exc:
        _log_failed(tool, exc)
        return err(exc, domain_code="not_found")
    except Exception as exc:
        _log_failed(tool, exc)
        return err(exc)
    logger.info(MCP_HANDLER_INVOKE_SUCCESS, tool_name=tool)
    return ok(data=status.model_dump(mode="json"))


async def _memory_cancel_fine_tune(
    *,
    app_state: Any,
    arguments: dict[str, Any],
    actor: AgentIdentity | None = None,
) -> str:
    tool = "synthorg_memory_cancel_fine_tune"
    try:
        reason, resolved_actor = require_destructive_guardrails(
            arguments,
            actor,
        )
    except GuardrailViolationError as exc:
        _log_guardrail(tool, exc)
        return err(exc)
    try:
        service = _service(app_state)
        await service.cancel_fine_tune()
    except BackendUnsupportedError as exc:
        return not_supported(tool, str(exc))
    except Exception as exc:
        _log_failed(tool, exc)
        return err(exc)
    logger.info(MCP_HANDLER_INVOKE_SUCCESS, tool_name=tool)
    logger.info(
        MCP_DESTRUCTIVE_OP_EXECUTED,
        tool_name=tool,
        actor_agent_id=_actor_id(resolved_actor),
        reason=reason,
    )
    return ok()


async def _memory_run_preflight(
    *,
    app_state: Any,
    arguments: dict[str, Any],
    actor: AgentIdentity | None = None,  # noqa: ARG001
) -> str:
    tool = "synthorg_memory_run_preflight"
    try:
        plan = _parse_fine_tune_plan(arguments)
    except ArgumentValidationError as exc:
        _log_invalid(tool, exc)
        return err(exc)
    try:
        service = _service(app_state)
        result = await service.run_preflight(plan)
    except BackendUnsupportedError as exc:
        return not_supported(tool, str(exc))
    except Exception as exc:
        _log_failed(tool, exc)
        return err(exc)
    logger.info(MCP_HANDLER_INVOKE_SUCCESS, tool_name=tool)
    return ok(data=result.model_dump(mode="json"))


async def _memory_list_checkpoints(
    *,
    app_state: Any,
    arguments: dict[str, Any],
    actor: AgentIdentity | None = None,  # noqa: ARG001
) -> str:
    tool = "synthorg_memory_list_checkpoints"
    try:
        offset, limit = coerce_pagination(arguments)
    except ArgumentValidationError as exc:
        _log_invalid(tool, exc)
        return err(exc)
    try:
        service = _service(app_state)
    except BackendUnsupportedError as exc:
        return not_supported(tool, str(exc))
    try:
        checkpoints, total = await service.list_checkpoints(
            limit=limit,
            offset=offset,
        )
    except Exception as exc:
        _log_failed(tool, exc)
        return err(exc)
    meta = PaginationMeta(total=total, offset=offset, limit=limit)
    logger.info(MCP_HANDLER_INVOKE_SUCCESS, tool_name=tool)
    return ok(data=dump_many(checkpoints), pagination=meta)


async def _memory_deploy_checkpoint(
    *,
    app_state: Any,
    arguments: dict[str, Any],
    actor: AgentIdentity | None = None,  # noqa: ARG001
) -> str:
    tool = "synthorg_memory_deploy_checkpoint"
    try:
        checkpoint_id = _require_non_blank(arguments, _ARG_CHECKPOINT_ID)
    except ArgumentValidationError as exc:
        _log_invalid(tool, exc)
        return err(exc)
    try:
        service = _service(app_state)
    except BackendUnsupportedError as exc:
        return not_supported(tool, str(exc))
    try:
        cp = await service.deploy_checkpoint(checkpoint_id)
    except CheckpointNotFoundError as exc:
        _log_failed(tool, exc)
        return err(exc, domain_code="not_found")
    except QueryError as exc:
        _log_failed(tool, exc)
        return err(exc, domain_code="conflict")
    except Exception as exc:
        _log_failed(tool, exc)
        return err(exc)
    logger.info(MCP_HANDLER_INVOKE_SUCCESS, tool_name=tool)
    return ok(data=cp.model_dump(mode="json"))


async def _memory_rollback_checkpoint(  # noqa: PLR0911
    *,
    app_state: Any,
    arguments: dict[str, Any],
    actor: AgentIdentity | None = None,
) -> str:
    tool = "synthorg_memory_rollback_checkpoint"
    try:
        checkpoint_id = _require_non_blank(arguments, _ARG_CHECKPOINT_ID)
    except ArgumentValidationError as exc:
        _log_invalid(tool, exc)
        return err(exc)
    try:
        reason, resolved_actor = require_destructive_guardrails(
            arguments,
            actor,
        )
    except GuardrailViolationError as exc:
        _log_guardrail(tool, exc)
        return err(exc)
    try:
        service = _service(app_state)
    except BackendUnsupportedError as exc:
        return not_supported(tool, str(exc))
    try:
        cp = await service.rollback_checkpoint(checkpoint_id)
    except CheckpointNotFoundError as exc:
        _log_failed(tool, exc)
        return err(exc, domain_code="not_found")
    except (
        CheckpointRollbackUnavailableError,
        CheckpointRollbackCorruptError,
    ) as exc:
        _log_failed(tool, exc)
        return err(exc, domain_code="conflict")
    except Exception as exc:
        _log_failed(tool, exc)
        return err(exc)
    logger.info(MCP_HANDLER_INVOKE_SUCCESS, tool_name=tool)
    logger.info(
        MCP_DESTRUCTIVE_OP_EXECUTED,
        tool_name=tool,
        actor_agent_id=_actor_id(resolved_actor),
        reason=reason,
        target_id=checkpoint_id,
    )
    return ok(data=cp.model_dump(mode="json"))


async def _memory_delete_checkpoint(  # noqa: PLR0911
    *,
    app_state: Any,
    arguments: dict[str, Any],
    actor: AgentIdentity | None = None,
) -> str:
    tool = "synthorg_memory_delete_checkpoint"
    try:
        checkpoint_id = _require_non_blank(arguments, _ARG_CHECKPOINT_ID)
    except ArgumentValidationError as exc:
        _log_invalid(tool, exc)
        return err(exc)
    try:
        reason, resolved_actor = require_destructive_guardrails(
            arguments,
            actor,
        )
    except GuardrailViolationError as exc:
        _log_guardrail(tool, exc)
        return err(exc)

    try:
        service = _service(app_state)
    except BackendUnsupportedError as exc:
        return not_supported(tool, str(exc))
    try:
        await service.delete_checkpoint(checkpoint_id)
    except CheckpointNotFoundError as exc:
        _log_failed(tool, exc)
        return err(exc, domain_code="not_found")
    except QueryError as exc:
        _log_failed(tool, exc)
        return err(exc, domain_code="conflict")
    except Exception as exc:
        _log_failed(tool, exc)
        return err(exc)

    logger.info(MCP_HANDLER_INVOKE_SUCCESS, tool_name=tool)
    logger.info(
        MCP_DESTRUCTIVE_OP_EXECUTED,
        tool_name=tool,
        actor_agent_id=_actor_id(resolved_actor),
        reason=reason,
        target_id=checkpoint_id,
    )
    return ok()


async def _memory_list_runs(
    *,
    app_state: Any,
    arguments: dict[str, Any],
    actor: AgentIdentity | None = None,  # noqa: ARG001
) -> str:
    tool = "synthorg_memory_list_runs"
    try:
        offset, limit = coerce_pagination(arguments)
    except ArgumentValidationError as exc:
        _log_invalid(tool, exc)
        return err(exc)
    try:
        service = _service(app_state)
    except BackendUnsupportedError as exc:
        return not_supported(tool, str(exc))
    try:
        runs, total = await service.list_runs(limit=limit, offset=offset)
    except Exception as exc:
        _log_failed(tool, exc)
        return err(exc)
    meta = PaginationMeta(total=total, offset=offset, limit=limit)
    logger.info(MCP_HANDLER_INVOKE_SUCCESS, tool_name=tool)
    return ok(data=dump_many(runs), pagination=meta)


async def _memory_get_active_embedder(
    *,
    app_state: Any,
    arguments: dict[str, Any],  # noqa: ARG001
    actor: AgentIdentity | None = None,  # noqa: ARG001
) -> str:
    tool = "synthorg_memory_get_active_embedder"
    try:
        service = _service(app_state)
    except BackendUnsupportedError as exc:
        return not_supported(tool, str(exc))
    try:
        snap = await service.get_active_embedder()
    except Exception as exc:
        _log_failed(tool, exc)
        return err(exc)
    logger.info(MCP_HANDLER_INVOKE_SUCCESS, tool_name=tool)
    return ok(data=snap.model_dump(mode="json"))


def _parse_fine_tune_plan(arguments: dict[str, Any]) -> FineTunePlan:
    """Build a :class:`FineTunePlan` from MCP arguments with typed errors."""
    source_dir = _require_non_blank(arguments, "source_dir")
    payload: dict[str, Any] = {"source_dir": NotBlankStr(source_dir)}
    for key in (
        "base_model",
        "output_dir",
        "resume_run_id",
    ):
        raw = arguments.get(key)
        if isinstance(raw, str) and raw.strip():
            payload[key] = NotBlankStr(raw.strip())
    for key in ("epochs", "top_k", "batch_size"):
        raw = arguments.get(key)
        if raw is None:
            continue
        if isinstance(raw, bool) or not isinstance(raw, int):
            raise invalid_argument(key, "positive int")
        payload[key] = raw
    for key in ("learning_rate", "temperature", "validation_split"):
        raw = arguments.get(key)
        if raw is None:
            continue
        if isinstance(raw, bool) or not isinstance(raw, (int, float)):
            raise invalid_argument(key, "positive float")
        payload[key] = float(raw)
    try:
        return FineTunePlan(**payload)
    except Exception as exc:
        arg_name = "plan"
        expected = "valid FineTunePlan shape"
        raise invalid_argument(arg_name, expected) from exc


MEMORY_HANDLERS: Mapping[str, ToolHandler] = MappingProxyType(
    copy.deepcopy(
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
    ),
)
