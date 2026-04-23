"""Budget domain MCP handlers.

Shims the 5 budget tools onto ``app_state.cost_tracker`` +
``app_state.config_resolver`` + ``app_state.persistence.budget_config_versions``.
All budget tools are reads; none are destructive.
"""

from types import MappingProxyType
from typing import TYPE_CHECKING, Any

from synthorg.meta.mcp.errors import ArgumentValidationError, invalid_argument
from synthorg.meta.mcp.handlers.common import (
    PaginationMeta,
    dump_many,
    err,
    ok,
    paginate_sequence,
    require_arg,
)
from synthorg.observability import get_logger, safe_error_description
from synthorg.observability.events.mcp import (
    MCP_HANDLER_ARGUMENT_INVALID,
    MCP_HANDLER_INVOKE_FAILED,
    MCP_HANDLER_INVOKE_SUCCESS,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from synthorg.meta.mcp.invoker import ToolHandler

logger = get_logger(__name__)


_TY_NON_BLANK = "non-blank string"
_TY_POS_INT = "positive int"
_TY_NON_NEG_INT = "non-negative int"
_ARG_AGENT_ID = "agent_id"
_ARG_TASK_ID = "task_id"
_ARG_VERSION = "version_num"
_ARG_OFFSET = "offset"
_ARG_LIMIT = "limit"
_ENTITY_ID = "default"


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


class _NotFoundError(LookupError):
    """Handler-local not-found signal (budget config version missing)."""

    domain_code = "not_found"


def _log_failed(tool: str, exc: Exception) -> None:
    logger.warning(
        MCP_HANDLER_INVOKE_FAILED,
        tool_name=tool,
        error_type=type(exc).__name__,
        error=safe_error_description(exc),
    )


def _log_invalid(tool: str, exc: Exception) -> None:
    logger.info(
        MCP_HANDLER_ARGUMENT_INVALID,
        tool_name=tool,
        error_type=type(exc).__name__,
        error=safe_error_description(exc),
    )


def _require_non_blank(arguments: dict[str, Any], key: str) -> str:
    raw = require_arg(arguments, key, str)
    if not raw.strip():
        raise invalid_argument(key, _TY_NON_BLANK)
    return raw


async def _budget_get_config(
    *,
    app_state: Any,
    arguments: dict[str, Any],  # noqa: ARG001
    actor: Any = None,  # noqa: ARG001
) -> str:
    tool = "synthorg_budget_get_config"
    try:
        config = await app_state.config_resolver.get_budget_config()
    except Exception as exc:
        _log_failed(tool, exc)
        return err(exc)
    logger.debug(MCP_HANDLER_INVOKE_SUCCESS, tool_name=tool)
    return ok(data=config.model_dump(mode="json"))


async def _budget_list_records(
    *,
    app_state: Any,
    arguments: dict[str, Any],
    actor: Any = None,  # noqa: ARG001
) -> str:
    tool = "synthorg_budget_list_records"
    try:
        agent_id = arguments.get("agent_id")
        task_id = arguments.get("task_id")
        if agent_id is not None and (
            not isinstance(agent_id, str) or not agent_id.strip()
        ):
            raise invalid_argument(_ARG_AGENT_ID, _TY_NON_BLANK)
        if task_id is not None and (
            not isinstance(task_id, str) or not task_id.strip()
        ):
            raise invalid_argument(_ARG_TASK_ID, _TY_NON_BLANK)
        offset, limit = _coerce_pagination(arguments)
    except ArgumentValidationError as exc:
        _log_invalid(tool, exc)
        return err(exc)

    try:
        records = await app_state.cost_tracker.get_records(
            agent_id=agent_id,
            task_id=task_id,
        )
        page, meta = paginate_sequence(records, offset=offset, limit=limit)
    except Exception as exc:
        _log_failed(tool, exc)
        return err(exc)
    logger.debug(MCP_HANDLER_INVOKE_SUCCESS, tool_name=tool)
    return ok(data=dump_many(page), pagination=meta)


async def _budget_get_agent_spending(
    *,
    app_state: Any,
    arguments: dict[str, Any],
    actor: Any = None,  # noqa: ARG001
) -> str:
    tool = "synthorg_budget_get_agent_spending"
    try:
        agent_id = _require_non_blank(arguments, _ARG_AGENT_ID)
    except ArgumentValidationError as exc:
        _log_invalid(tool, exc)
        return err(exc)

    try:
        total = await app_state.cost_tracker.get_agent_cost(agent_id)
        config = await app_state.config_resolver.get_budget_config()
    except Exception as exc:
        _log_failed(tool, exc)
        return err(exc)
    logger.debug(MCP_HANDLER_INVOKE_SUCCESS, tool_name=tool)
    return ok(
        data={
            "agent_id": agent_id,
            "total_cost": total,
            "currency": config.currency,
        },
    )


async def _budget_versions_list(
    *,
    app_state: Any,
    arguments: dict[str, Any],
    actor: Any = None,  # noqa: ARG001
) -> str:
    tool = "synthorg_budget_versions_list"
    try:
        offset, limit = _coerce_pagination(arguments)
    except ArgumentValidationError as exc:
        _log_invalid(tool, exc)
        return err(exc)

    try:
        repo = app_state.persistence.budget_config_versions
        versions = await repo.list_versions(_ENTITY_ID, limit=limit, offset=offset)
        total = await repo.count_versions(_ENTITY_ID)
    except Exception as exc:
        _log_failed(tool, exc)
        return err(exc)
    # The repo already returned the requested page; don't re-paginate.
    # Build the envelope meta directly with the repo's true total.
    meta = PaginationMeta(total=total, offset=offset, limit=limit)
    logger.debug(MCP_HANDLER_INVOKE_SUCCESS, tool_name=tool)
    return ok(data=dump_many(versions), pagination=meta)


async def _budget_versions_get(
    *,
    app_state: Any,
    arguments: dict[str, Any],
    actor: Any = None,  # noqa: ARG001
) -> str:
    tool = "synthorg_budget_versions_get"
    try:
        version_num = require_arg(arguments, _ARG_VERSION, int)
        if version_num < 1:
            raise invalid_argument(_ARG_VERSION, _TY_POS_INT)
    except ArgumentValidationError as exc:
        _log_invalid(tool, exc)
        return err(exc)

    try:
        repo = app_state.persistence.budget_config_versions
        snapshot = await repo.get_version(_ENTITY_ID, version_num)
    except Exception as exc:
        _log_failed(tool, exc)
        return err(exc)
    if snapshot is None:
        missing = _NotFoundError(
            f"Budget config version {version_num} not found",
        )
        _log_failed(tool, missing)
        return err(missing)
    logger.debug(MCP_HANDLER_INVOKE_SUCCESS, tool_name=tool)
    return ok(data=snapshot.model_dump(mode="json"))


BUDGET_HANDLERS: Mapping[str, ToolHandler] = MappingProxyType(
    {
        "synthorg_budget_get_config": _budget_get_config,
        "synthorg_budget_list_records": _budget_list_records,
        "synthorg_budget_get_agent_spending": _budget_get_agent_spending,
        "synthorg_budget_versions_list": _budget_versions_list,
        "synthorg_budget_versions_get": _budget_versions_get,
    },
)
