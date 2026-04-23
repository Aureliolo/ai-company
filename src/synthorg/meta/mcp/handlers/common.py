"""Shared helpers for MCP tool handlers.

Every real handler imports from this module.  The file provides three
concerns in one place:

1. **Response envelope** (``ok``, ``err``, ``PaginationMeta``) -- builds
   the JSON string the handler returns to the invoker.
2. **Input helpers** (``require_arg``, ``dump_many``,
   ``paginate_sequence``) -- typed extraction, Pydantic serialisation,
   in-memory pagination.
3. **Guardrails** (``require_destructive_guardrails``) -- single source
   of truth for the ``confirm=True`` + non-blank ``reason`` + non-None
   ``actor`` triple enforced on every destructive tool.

The placeholder scaffold (``make_placeholder_handler``,
``make_handlers_for_tools``) stays in this module; real handlers never
call it.  The placeholder now logs at WARNING (upgraded from DEBUG in
HYG-1) via the new ``MCP_HANDLER_NOT_IMPLEMENTED`` event so ops can
alert on unwired tools.
"""

import json
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field

from synthorg.meta.mcp.errors import guardrail_violation, invalid_argument
from synthorg.observability import get_logger, safe_error_description
from synthorg.observability.events.mcp import MCP_HANDLER_NOT_IMPLEMENTED

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

logger = get_logger(__name__)

_ARG_OFFSET = "offset"
_ARG_LIMIT = "limit"
_TY_NON_NEG_INT = "non-negative int"
_TY_POS_INT = "positive int"

_GR_MISSING_ACTOR = "missing_actor"
_GR_MISSING_CONFIRM = "missing_confirm"
_GR_MISSING_REASON = "missing_reason"
_GR_MSG_ACTOR = "Destructive operation requires an identified actor"
_GR_MSG_CONFIRM = "Destructive operation requires 'confirm': true"
_GR_MSG_REASON = "Destructive operation requires a non-blank 'reason'"


class PaginationMeta(BaseModel):
    """Pagination metadata attached to list/collection responses.

    Attributes:
        total: Unfiltered total count as reported by the service.
            Never synthesised by the handler; always the service's
            own number.
        offset: Starting offset applied to this page.
        limit: Page size applied to this page.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    total: int = Field(ge=0)
    offset: int = Field(ge=0)
    limit: int = Field(gt=0)


def ok(
    data: Any = None,
    *,
    pagination: PaginationMeta | None = None,
) -> str:
    """Build an ``ok`` success envelope as a JSON string.

    Args:
        data: JSON-serialisable payload (dict / list / scalar / ``None``).
            When ``None``, no ``data`` key is included.  Pydantic models
            must be pre-dumped by the caller via ``.model_dump(mode="json")``
            or the ``dump_many`` helper.
        pagination: Optional pagination metadata; present only on
            list/collection responses.

    Returns:
        JSON-encoded envelope suitable for direct return from an MCP
        tool handler.
    """
    body: dict[str, Any] = {"status": "ok"}
    if data is not None:
        body["data"] = data
    if pagination is not None:
        body["pagination"] = pagination.model_dump(mode="json")
    return json.dumps(body)


def err(
    exc: Exception,
    *,
    domain_code: str | None = None,
) -> str:
    """Build a domain-error envelope as a JSON string.

    ``message`` goes through ``safe_error_description`` so tracebacks
    and frame-local state never leak into the envelope (SEC-1).

    Args:
        exc: The caught exception.
        domain_code: Optional explicit code; when omitted falls back to
            ``exc.domain_code`` (set by ``ArgumentValidationError`` /
            ``GuardrailViolationError``) and is otherwise absent.

    Returns:
        JSON-encoded envelope with ``status="error"``.
    """
    body: dict[str, Any] = {
        "status": "error",
        "error_type": type(exc).__name__,
        "message": safe_error_description(exc),
    }
    resolved_code = (
        domain_code
        if domain_code is not None
        else getattr(
            exc,
            "domain_code",
            None,
        )
    )
    if resolved_code is not None:
        body["domain_code"] = resolved_code
    return json.dumps(body)


def require_arg[T](arguments: dict[str, Any], key: str, ty: type[T]) -> T:
    """Extract a typed required argument or raise ``ArgumentValidationError``.

    ``bool`` is explicitly rejected when ``ty is int`` so that a sloppy
    ``confirm=True`` never satisfies an int field.  ``None`` is always
    treated as missing, regardless of the declared type.

    Args:
        arguments: Parsed tool arguments.
        key: Argument name.
        ty: Expected Python type (``str``, ``int``, ``bool``, etc.).

    Returns:
        The argument value, narrowed to ``ty``.

    Raises:
        ArgumentValidationError: If missing, ``None``, or wrongly typed.
    """
    if key not in arguments or arguments[key] is None:
        raise invalid_argument(key, ty.__name__)
    value = arguments[key]
    if ty is int and isinstance(value, bool):
        raise invalid_argument(key, "int")
    if not isinstance(value, ty):
        raise invalid_argument(key, ty.__name__)
    return value


def require_destructive_guardrails(
    arguments: dict[str, Any],
    actor: Any,
) -> tuple[str, Any]:
    """Enforce the destructive-op precondition triple.

    A tool is destructive if it removes, cancels, rejects, rolls back,
    or uninstalls state (see plan for the canonical list).  Every such
    tool's handler calls this helper first.

    Preconditions, in order:
    1. ``actor`` is not ``None`` (the invoker thread-through populated it);
    2. ``arguments["confirm"]`` is the Python literal ``True`` (not
       truthy-but-non-bool);
    3. ``arguments["reason"]`` is a non-blank string.

    Args:
        arguments: Parsed tool arguments.
        actor: The calling agent identity, or ``None`` when the invoker
            was not supplied one.

    Returns:
        Tuple of (reason, actor) -- both already validated.

    Raises:
        GuardrailViolationError: On any precondition failure.  The
            ``violation`` attribute distinguishes the failure mode.
    """
    if actor is None:
        raise guardrail_violation(_GR_MISSING_ACTOR, _GR_MSG_ACTOR)
    confirm = arguments.get("confirm")
    if not isinstance(confirm, bool) or confirm is not True:
        raise guardrail_violation(_GR_MISSING_CONFIRM, _GR_MSG_CONFIRM)
    reason = arguments.get("reason")
    if not isinstance(reason, str) or not reason.strip():
        raise guardrail_violation(_GR_MISSING_REASON, _GR_MSG_REASON)
    return reason, actor


def dump_many(models: Iterable[BaseModel]) -> list[dict[str, Any]]:
    """Serialise a batch of Pydantic models to JSON-mode dicts.

    Args:
        models: Any iterable (tuple, list, generator) of Pydantic models.

    Returns:
        List of dicts, one per input model, suitable for inclusion in
        an ``ok(data=...)`` envelope.
    """
    return [m.model_dump(mode="json") for m in models]


def paginate_sequence[T](
    seq: Sequence[T],
    *,
    offset: int,
    limit: int,
    total: int | None = None,
) -> tuple[list[T], PaginationMeta]:
    """Slice an already-materialised sequence into a page + metadata.

    Used when the underlying service returns the full collection in one
    call (typical of aggregator-style domains: signals, parts of
    analytics).  Services that natively accept offset/limit should
    translate arguments and return ``(items, total)`` directly rather
    than calling this helper.

    Args:
        seq: Full collection from the service.
        offset: Page offset.
        limit: Page size.
        total: Unfiltered total count as reported by the service.  When
            omitted, falls back to ``len(seq)`` (valid iff ``seq`` is
            already the full set).

    Returns:
        Tuple of (page slice, pagination metadata).

    Raises:
        ArgumentValidationError: If ``offset`` is negative or ``limit``
            is non-positive.
    """
    if offset < 0:
        raise invalid_argument(_ARG_OFFSET, _TY_NON_NEG_INT)
    if limit <= 0:
        raise invalid_argument(_ARG_LIMIT, _TY_POS_INT)
    resolved_total = total if total is not None else len(seq)
    page = list(seq[offset : offset + limit])
    return page, PaginationMeta(total=resolved_total, offset=offset, limit=limit)


def make_placeholder_handler(tool_name: str) -> Any:
    """Create a placeholder handler that returns a not-implemented message.

    Used for tools whose service layer integration is pending.  The
    handler returns a structured JSON response indicating the tool is
    registered but not yet wired to the service layer.  Emits at
    WARNING so ops can alert on unwired tools in production.

    Args:
        tool_name: Tool name for the message.

    Returns:
        Async handler function.
    """

    async def handler(
        *,
        app_state: Any,  # noqa: ARG001
        arguments: dict[str, Any],
        actor: Any = None,  # noqa: ARG001
    ) -> str:
        logger.warning(
            MCP_HANDLER_NOT_IMPLEMENTED,
            tool_name=tool_name,
        )
        return json.dumps(
            {
                "status": "not_implemented",
                "tool": tool_name,
                "message": (
                    f"Tool {tool_name!r} is registered but its service "
                    f"layer handler is not yet implemented."
                ),
                "arguments_received": arguments,
            }
        )

    return handler


def make_handlers_for_tools(
    tool_names: tuple[str, ...],
) -> dict[str, Any]:
    """Create placeholder handlers for a set of tool names.

    Args:
        tool_names: Tuple of tool name strings.

    Returns:
        Dict mapping tool names to placeholder handlers.
    """
    return {name: make_placeholder_handler(name) for name in tool_names}
