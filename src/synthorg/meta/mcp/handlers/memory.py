"""Memory domain MCP handlers (fine-tune checkpoints + runs).

11 tools, all wired through :class:`MemoryService` after META-MCP-4.
The service is injected via ``app_state.memory_service`` by the
application bootstrap; handlers route through that facade exclusively
and never reach into ``app_state.persistence.*`` directly (CLAUDE.md
persistence-boundary rule).

Backend-unsupported routing. Any attempt to invoke a fine-tune
lifecycle method on a service without an orchestrator (or against a
persistence backend that lacks fine-tune repos) raises
:class:`BackendUnsupportedError`. When no :class:`MemoryService` is
wired at all (stripped-down test app-states, or unsupported backends),
:func:`_service` raises the same exception. Handlers catch it and
forward to :func:`not_supported`, which both:

- returns the shared ``not_supported`` wire envelope
  (``{"status": "error", "domain_code": "not_supported"}``), and
- emits the :data:`MCP_HANDLER_NOT_IMPLEMENTED` WARNING event so ops
  telemetry can distinguish backend-unsupported from fully-wired but
  method-missing primitives (``capability_gap`` path).

Destructive ops. ``cancel_fine_tune``, ``rollback_checkpoint``, and
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


_WHY_MEMORY_SERVICE_NOT_WIRED = (
    "memory service is not wired on the active application state; "
    "fine-tune endpoints require an injected MemoryService and are "
    "unavailable on backends that do not support fine-tune repositories"
)


def _service(app_state: Any) -> MemoryService:
    """Return the injected :class:`MemoryService` facade.

    Handlers route through ``app_state.memory_service`` exclusively
    (CLAUDE.md persistence-boundary rule). If no service is wired --
    either the application bootstrap skipped the setter (stripped-down
    test app-states) or the active backend does not support fine-tune
    repositories -- we raise :class:`BackendUnsupportedError` so the
    calling handler returns a clean ``not_supported`` envelope.

    Raises:
        BackendUnsupportedError: When ``app_state.memory_service``
            is not set.
    """
    if getattr(app_state, "has_memory_service", False):
        attached: MemoryService = app_state.memory_service
        return attached
    raise BackendUnsupportedError(_WHY_MEMORY_SERVICE_NOT_WIRED)


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
    except MemoryError, RecursionError:
        raise
    except RuntimeError as exc:
        # ``MemoryService.start_fine_tune`` raises ``RuntimeError``
        # when another run is already active; surface that as a
        # conflict so callers get a typed recovery path instead of
        # a generic handler error.
        _log_failed(tool, exc)
        return err(exc, domain_code="conflict")
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
    except MemoryError, RecursionError:
        raise
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
    except MemoryError, RecursionError:
        raise
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
    except MemoryError, RecursionError:
        raise
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
    except MemoryError, RecursionError:
        raise
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
    except MemoryError, RecursionError:
        raise
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
        # Persistence-layer failure during deploy (e.g. the checkpoint
        # was activated but the re-read failed) -- surface as
        # ``conflict`` so callers distinguish from internal errors.
        _log_failed(tool, exc)
        return err(exc, domain_code="conflict")
    except MemoryError, RecursionError:
        raise
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
    except MemoryError, RecursionError:
        raise
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
        # Active-checkpoint / domain-rule violation -- surface as
        # ``conflict`` so callers can distinguish from internal errors.
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
    except MemoryError, RecursionError:
        raise
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
    except MemoryError, RecursionError:
        raise
    except Exception as exc:
        _log_failed(tool, exc)
        return err(exc)
    logger.info(MCP_HANDLER_INVOKE_SUCCESS, tool_name=tool)
    return ok(data=snap.model_dump(mode="json"))


_OPTIONAL_STR_KEYS: tuple[str, ...] = (
    "base_model",
    "output_dir",
    "resume_run_id",
)
_OPTIONAL_INT_KEYS: tuple[str, ...] = ("epochs", "top_k", "batch_size")
_OPTIONAL_FLOAT_KEYS: tuple[str, ...] = (
    "learning_rate",
    "temperature",
    "validation_split",
)


def _collect_optional_strings(
    arguments: dict[str, Any],
    payload: dict[str, Any],
) -> None:
    for key in _OPTIONAL_STR_KEYS:
        if key not in arguments:
            continue
        raw = arguments[key]
        if raw is None:
            continue
        if not isinstance(raw, str) or not raw.strip():
            # Reject present-but-malformed values (e.g. ``""`` or a
            # non-string) instead of silently dropping them -- otherwise
            # ``resume_run_id=""`` would become a fresh fine-tune rather
            # than an ``invalid_argument`` response.
            raise invalid_argument(key, _TY_NON_BLANK)
        payload[key] = NotBlankStr(raw.strip())


def _collect_optional_ints(
    arguments: dict[str, Any],
    payload: dict[str, Any],
) -> None:
    for key in _OPTIONAL_INT_KEYS:
        raw = arguments.get(key)
        if raw is None:
            continue
        if isinstance(raw, bool) or not isinstance(raw, int):
            raise invalid_argument(key, "positive int")
        payload[key] = raw


def _collect_optional_floats(
    arguments: dict[str, Any],
    payload: dict[str, Any],
) -> None:
    for key in _OPTIONAL_FLOAT_KEYS:
        raw = arguments.get(key)
        if raw is None:
            continue
        if isinstance(raw, bool) or not isinstance(raw, (int, float)):
            raise invalid_argument(key, "positive float")
        payload[key] = float(raw)


def _parse_fine_tune_plan(arguments: dict[str, Any]) -> FineTunePlan:
    """Build a :class:`FineTunePlan` from MCP arguments with typed errors."""
    source_dir = _require_non_blank(arguments, "source_dir")
    payload: dict[str, Any] = {"source_dir": NotBlankStr(source_dir)}
    _collect_optional_strings(arguments, payload)
    _collect_optional_ints(arguments, payload)
    _collect_optional_floats(arguments, payload)
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
