"""Memory domain MCP handlers (fine-tune checkpoints + runs).

11 tools.  Reads (``list_checkpoints``, ``list_runs``) shim to
:class:`synthorg.memory.service.MemoryService` built per-call from
the persistence backend.  The fine-tune pipeline orchestration
methods (start/resume/cancel/run_preflight/deploy) require additional
state not exposed through a clean MCP arg set, so they return
``capability_gap`` until a dedicated design pass lands.

Destructive ops: ``cancel_fine_tune``, ``rollback_checkpoint``, and
``delete_checkpoint`` all enforce the guardrail triple at the handler
boundary.  ``delete_checkpoint`` is live; the others are currently
``capability_gap`` behind the guardrail.
"""

import copy
from collections.abc import Mapping  # noqa: TC003 -- PEP 649 annotation
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
from synthorg.persistence.errors import PersistenceConnectionError, QueryError

if TYPE_CHECKING:
    from synthorg.core.agent import AgentIdentity

logger = get_logger(__name__)


_TY_NON_BLANK = "non-blank string"
_ARG_CHECKPOINT_ID = "checkpoint_id"


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
    """Extract a non-blank string argument, stripped of surrounding whitespace.

    Normalising at the boundary keeps downstream service lookups
    consistent -- a ``checkpoint_id`` like ``"  cp-123  "`` would
    otherwise fail the repository's exact-match lookup.
    """
    raw = arguments.get(key)
    if not isinstance(raw, str) or not raw.strip():
        raise invalid_argument(key, _TY_NON_BLANK)
    return raw.strip()


class _BackendLacksFineTuneError(Exception):
    """Raised when the active persistence backend lacks fine-tune repos."""


def _service(app_state: Any) -> MemoryService:
    """Return the memory service facade.

    Prefers ``app_state.memory_service`` when bootstrap has wired one
    (keeps handlers off ``persistence.*``).  Falls back to per-call
    construction from the persistence backend for app_states that have
    not adopted the cached-service pattern yet.  Accessor calls raise
    :class:`_BackendLacksFineTuneError` so the calling handler can
    return a clean ``capability_gap`` envelope instead of bubbling up
    a raw backend exception.  Two conditions trigger this:

    * The backend's implementation of a fine-tune property raises
      ``NotImplementedError`` (legacy / partial backend).
    * The backend is not yet connected, and the property's
      ``_require_connected`` guard raises
      :class:`~synthorg.persistence.errors.PersistenceConnectionError`.

    Raises:
        _BackendLacksFineTuneError: If the backend does not implement
            the fine-tune repositories *or* is not currently connected.
    """
    cached: MemoryService | None = getattr(app_state, "memory_service", None)
    if cached is not None:
        return cached
    backend = app_state.persistence
    try:
        checkpoint_repo = backend.fine_tune_checkpoints
        run_repo = backend.fine_tune_runs
    except (NotImplementedError, PersistenceConnectionError) as exc:
        raise _BackendLacksFineTuneError(_WHY_BACKEND_NO_FINE_TUNE) from exc
    has_settings = getattr(app_state, "has_settings_service", False)
    return MemoryService(
        checkpoint_repo=checkpoint_repo,
        run_repo=run_repo,
        settings_service=(
            getattr(app_state, "settings_service", None) if has_settings else None
        ),
    )


_WHY_FINE_TUNE_START = (
    "fine-tune pipeline orchestration needs a TrainingPlan and a "
    "worker handle; no MCP-native schema exists yet"
)
_WHY_FINE_TUNE_CANCEL = (
    "fine-tune cancellation needs the orchestrator run_id + cancel "
    "token context MCP does not yet plumb through; use the fine-tune "
    "controller"
)
_WHY_FINE_TUNE_PREFLIGHT = (
    "preflight validation runs inside the fine-tune controller; no "
    "standalone service method is exposed"
)
_WHY_FINE_TUNE_STATUS = (
    "fine-tune status queries require the orchestrator run_id context "
    "that MCP does not yet plumb through; use the fine-tune controller"
)
_WHY_RUNS = (
    "fine-tune run listing is served by the fine-tune controller; "
    "MemoryService does not expose a list method yet"
)
_WHY_EMBEDDER = (
    "active-embedder metadata is read from settings_service; no "
    "dedicated query method on MemoryService"
)
_WHY_BACKEND_NO_FINE_TUNE = (
    "fine-tune repositories are not exposed by the active persistence "
    "backend; ensure the backend is connected and exposes "
    "fine_tune_runs + fine_tune_checkpoints (both SQLite and Postgres "
    "do today)"
)


# --- handlers -------------------------------------------------------------


async def _memory_start_fine_tune(
    *,
    app_state: Any,  # noqa: ARG001
    arguments: dict[str, Any],  # noqa: ARG001
    actor: AgentIdentity | None = None,  # noqa: ARG001
) -> str:
    return capability_gap("synthorg_memory_start_fine_tune", _WHY_FINE_TUNE_START)


async def _memory_resume_fine_tune(
    *,
    app_state: Any,  # noqa: ARG001
    arguments: dict[str, Any],  # noqa: ARG001
    actor: AgentIdentity | None = None,  # noqa: ARG001
) -> str:
    return capability_gap("synthorg_memory_resume_fine_tune", _WHY_FINE_TUNE_START)


async def _memory_get_fine_tune_status(
    *,
    app_state: Any,  # noqa: ARG001
    arguments: dict[str, Any],  # noqa: ARG001
    actor: AgentIdentity | None = None,  # noqa: ARG001
) -> str:
    return capability_gap(
        "synthorg_memory_get_fine_tune_status",
        _WHY_FINE_TUNE_STATUS,
    )


async def _memory_cancel_fine_tune(
    *,
    app_state: Any,  # noqa: ARG001
    arguments: dict[str, Any],
    actor: AgentIdentity | None = None,
) -> str:
    tool = "synthorg_memory_cancel_fine_tune"
    try:
        require_destructive_guardrails(arguments, actor)
    except GuardrailViolationError as exc:
        _log_guardrail(tool, exc)
        return err(exc)
    return capability_gap(tool, _WHY_FINE_TUNE_CANCEL)


async def _memory_run_preflight(
    *,
    app_state: Any,  # noqa: ARG001
    arguments: dict[str, Any],  # noqa: ARG001
    actor: AgentIdentity | None = None,  # noqa: ARG001
) -> str:
    return capability_gap(
        "synthorg_memory_run_preflight",
        _WHY_FINE_TUNE_PREFLIGHT,
    )


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
    except _BackendLacksFineTuneError:
        return capability_gap(tool, _WHY_BACKEND_NO_FINE_TUNE)
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
    except _BackendLacksFineTuneError:
        return capability_gap(tool, _WHY_BACKEND_NO_FINE_TUNE)
    try:
        cp = await service.deploy_checkpoint(checkpoint_id)
    except CheckpointNotFoundError as exc:
        _log_failed(tool, exc)
        return err(exc, domain_code="not_found")
    except QueryError as exc:
        # Persistence-layer failure during deploy (e.g. the checkpoint
        # was activated but the re-read failed) -- surface as a
        # ``conflict`` so callers distinguish from internal errors.
        _log_failed(tool, exc)
        return err(exc, domain_code="conflict")
    except Exception as exc:
        _log_failed(tool, exc)
        return err(exc)
    logger.info(MCP_HANDLER_INVOKE_SUCCESS, tool_name=tool)
    return ok(data=cp.model_dump(mode="json"))


async def _memory_rollback_checkpoint(
    *,
    app_state: Any,  # noqa: ARG001
    arguments: dict[str, Any],
    actor: AgentIdentity | None = None,
) -> str:
    tool = "synthorg_memory_rollback_checkpoint"
    try:
        require_destructive_guardrails(arguments, actor)
    except GuardrailViolationError as exc:
        _log_guardrail(tool, exc)
        return err(exc)
    return capability_gap(
        tool,
        "rollback requires prior-active capture; only the fine-tune "
        "controller has access to that context today",
    )


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
        reason, _ = require_destructive_guardrails(arguments, actor)
    except GuardrailViolationError as exc:
        _log_guardrail(tool, exc)
        return err(exc)

    try:
        service = _service(app_state)
    except _BackendLacksFineTuneError:
        return capability_gap(tool, _WHY_BACKEND_NO_FINE_TUNE)
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
    except Exception as exc:
        _log_failed(tool, exc)
        return err(exc)

    logger.info(MCP_HANDLER_INVOKE_SUCCESS, tool_name=tool)
    logger.info(
        MCP_DESTRUCTIVE_OP_EXECUTED,
        tool_name=tool,
        actor_agent_id=_actor_id(actor),
        reason=reason,
        target_id=checkpoint_id,
    )
    return ok()


async def _memory_list_runs(
    *,
    app_state: Any,  # noqa: ARG001
    arguments: dict[str, Any],  # noqa: ARG001
    actor: AgentIdentity | None = None,  # noqa: ARG001
) -> str:
    return capability_gap("synthorg_memory_list_runs", _WHY_RUNS)


async def _memory_get_active_embedder(
    *,
    app_state: Any,  # noqa: ARG001
    arguments: dict[str, Any],  # noqa: ARG001
    actor: AgentIdentity | None = None,  # noqa: ARG001
) -> str:
    return capability_gap("synthorg_memory_get_active_embedder", _WHY_EMBEDDER)


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
