"""Communication domain MCP handlers.

21 tools spanning messages, meetings, connections, webhooks, and the
sandbox tunnel.  Service coverage is uneven:

- ``meetings.*`` leans on ``app_state.meeting_scheduler``.
- ``messages.*``, ``connections.*``, ``webhooks.*``, and ``tunnel.*``
  all live in their own API controllers without a consolidated service
  facade on ``app_state``; handlers return ``not_supported`` until a
  facade lands.

Destructive ops (``*_delete``) require the standard guardrail triple
and, where the underlying service is live, emit
``MCP_DESTRUCTIVE_OP_EXECUTED`` on success.
"""

from collections.abc import Mapping  # noqa: TC003 -- PEP 649 annotation
from types import MappingProxyType
from typing import TYPE_CHECKING, Any

from synthorg.meta.mcp.errors import GuardrailViolationError
from synthorg.meta.mcp.handler_protocol import (
    ToolHandler,  # noqa: TC001 -- PEP 649 annotation
)
from synthorg.meta.mcp.handlers.common import (
    err,
    not_supported,
    require_destructive_guardrails,
)
from synthorg.observability import get_logger
from synthorg.observability.events.mcp import MCP_HANDLER_GUARDRAIL_VIOLATED

if TYPE_CHECKING:
    from synthorg.core.agent import AgentIdentity

logger = get_logger(__name__)


_WHY_MESSAGES = (
    "messages are routed through the API controller + delegation store; "
    "no MessageService facade is attached to app_state"
)
_WHY_CONNECTIONS = (
    "connection CRUD lives behind the connections controller; no "
    "ConnectionService facade is on app_state"
)
_WHY_WEBHOOKS = (
    "webhook CRUD lives behind the webhooks controller; no "
    "WebhookService facade is on app_state"
)
_WHY_TUNNEL = (
    "tunnel lifecycle is orchestrated by the operations script; no "
    "TunnelService facade is on app_state"
)
_WHY_MEETING_WRITE = (
    "meeting CRUD expects full MeetingRecord schema; use the meetings "
    "REST API until an MCP-native schema is designed"
)


def _log_guardrail(tool: str, exc: GuardrailViolationError) -> None:
    logger.warning(
        MCP_HANDLER_GUARDRAIL_VIOLATED,
        tool_name=tool,
        violation=exc.violation,
    )


async def _enforce_destructive(
    tool: str,
    arguments: dict[str, Any],
    actor: AgentIdentity | None,
    why: str,
) -> str:
    try:
        require_destructive_guardrails(arguments, actor)
    except GuardrailViolationError as exc:
        _log_guardrail(tool, exc)
        return err(exc)
    return not_supported(tool, why)


# --- messages -------------------------------------------------------------


async def _messages_list(
    *,
    app_state: Any,  # noqa: ARG001
    arguments: dict[str, Any],  # noqa: ARG001
    actor: AgentIdentity | None = None,  # noqa: ARG001
) -> str:
    return not_supported("synthorg_messages_list", _WHY_MESSAGES)


async def _messages_get(
    *,
    app_state: Any,  # noqa: ARG001
    arguments: dict[str, Any],  # noqa: ARG001
    actor: AgentIdentity | None = None,  # noqa: ARG001
) -> str:
    return not_supported("synthorg_messages_get", _WHY_MESSAGES)


async def _messages_send(
    *,
    app_state: Any,  # noqa: ARG001
    arguments: dict[str, Any],  # noqa: ARG001
    actor: AgentIdentity | None = None,  # noqa: ARG001
) -> str:
    return not_supported("synthorg_messages_send", _WHY_MESSAGES)


async def _messages_delete(
    *,
    app_state: Any,  # noqa: ARG001
    arguments: dict[str, Any],
    actor: AgentIdentity | None = None,
) -> str:
    return await _enforce_destructive(
        "synthorg_messages_delete",
        arguments,
        actor,
        _WHY_MESSAGES,
    )


# --- meetings -------------------------------------------------------------


async def _meetings_list(
    *,
    app_state: Any,  # noqa: ARG001
    arguments: dict[str, Any],  # noqa: ARG001
    actor: AgentIdentity | None = None,  # noqa: ARG001
) -> str:
    return not_supported(
        "synthorg_meetings_list",
        "meeting history reads via the meetings REST controller; no "
        "list method is exposed on MeetingScheduler",
    )


async def _meetings_get(
    *,
    app_state: Any,  # noqa: ARG001
    arguments: dict[str, Any],  # noqa: ARG001
    actor: AgentIdentity | None = None,  # noqa: ARG001
) -> str:
    return not_supported("synthorg_meetings_get", _WHY_MEETING_WRITE)


async def _meetings_create(
    *,
    app_state: Any,  # noqa: ARG001
    arguments: dict[str, Any],  # noqa: ARG001
    actor: AgentIdentity | None = None,  # noqa: ARG001
) -> str:
    return not_supported("synthorg_meetings_create", _WHY_MEETING_WRITE)


async def _meetings_update(
    *,
    app_state: Any,  # noqa: ARG001
    arguments: dict[str, Any],  # noqa: ARG001
    actor: AgentIdentity | None = None,  # noqa: ARG001
) -> str:
    return not_supported("synthorg_meetings_update", _WHY_MEETING_WRITE)


async def _meetings_delete(
    *,
    app_state: Any,  # noqa: ARG001
    arguments: dict[str, Any],
    actor: AgentIdentity | None = None,
) -> str:
    return await _enforce_destructive(
        "synthorg_meetings_delete",
        arguments,
        actor,
        _WHY_MEETING_WRITE,
    )


# --- connections ----------------------------------------------------------


async def _connections_list(
    *,
    app_state: Any,  # noqa: ARG001
    arguments: dict[str, Any],  # noqa: ARG001
    actor: AgentIdentity | None = None,  # noqa: ARG001
) -> str:
    return not_supported("synthorg_connections_list", _WHY_CONNECTIONS)


async def _connections_get(
    *,
    app_state: Any,  # noqa: ARG001
    arguments: dict[str, Any],  # noqa: ARG001
    actor: AgentIdentity | None = None,  # noqa: ARG001
) -> str:
    return not_supported("synthorg_connections_get", _WHY_CONNECTIONS)


async def _connections_create(
    *,
    app_state: Any,  # noqa: ARG001
    arguments: dict[str, Any],  # noqa: ARG001
    actor: AgentIdentity | None = None,  # noqa: ARG001
) -> str:
    return not_supported("synthorg_connections_create", _WHY_CONNECTIONS)


async def _connections_delete(
    *,
    app_state: Any,  # noqa: ARG001
    arguments: dict[str, Any],
    actor: AgentIdentity | None = None,
) -> str:
    return await _enforce_destructive(
        "synthorg_connections_delete",
        arguments,
        actor,
        _WHY_CONNECTIONS,
    )


async def _connections_check_health(
    *,
    app_state: Any,  # noqa: ARG001
    arguments: dict[str, Any],  # noqa: ARG001
    actor: AgentIdentity | None = None,  # noqa: ARG001
) -> str:
    return not_supported("synthorg_connections_check_health", _WHY_CONNECTIONS)


# --- webhooks -------------------------------------------------------------


async def _webhooks_list(
    *,
    app_state: Any,  # noqa: ARG001
    arguments: dict[str, Any],  # noqa: ARG001
    actor: AgentIdentity | None = None,  # noqa: ARG001
) -> str:
    return not_supported("synthorg_webhooks_list", _WHY_WEBHOOKS)


async def _webhooks_get(
    *,
    app_state: Any,  # noqa: ARG001
    arguments: dict[str, Any],  # noqa: ARG001
    actor: AgentIdentity | None = None,  # noqa: ARG001
) -> str:
    return not_supported("synthorg_webhooks_get", _WHY_WEBHOOKS)


async def _webhooks_create(
    *,
    app_state: Any,  # noqa: ARG001
    arguments: dict[str, Any],  # noqa: ARG001
    actor: AgentIdentity | None = None,  # noqa: ARG001
) -> str:
    return not_supported("synthorg_webhooks_create", _WHY_WEBHOOKS)


async def _webhooks_update(
    *,
    app_state: Any,  # noqa: ARG001
    arguments: dict[str, Any],  # noqa: ARG001
    actor: AgentIdentity | None = None,  # noqa: ARG001
) -> str:
    return not_supported("synthorg_webhooks_update", _WHY_WEBHOOKS)


async def _webhooks_delete(
    *,
    app_state: Any,  # noqa: ARG001
    arguments: dict[str, Any],
    actor: AgentIdentity | None = None,
) -> str:
    return await _enforce_destructive(
        "synthorg_webhooks_delete",
        arguments,
        actor,
        _WHY_WEBHOOKS,
    )


# --- tunnel ---------------------------------------------------------------


async def _tunnel_get_status(
    *,
    app_state: Any,  # noqa: ARG001
    arguments: dict[str, Any],  # noqa: ARG001
    actor: AgentIdentity | None = None,  # noqa: ARG001
) -> str:
    return not_supported("synthorg_tunnel_get_status", _WHY_TUNNEL)


async def _tunnel_connect(
    *,
    app_state: Any,  # noqa: ARG001
    arguments: dict[str, Any],  # noqa: ARG001
    actor: AgentIdentity | None = None,  # noqa: ARG001
) -> str:
    return not_supported("synthorg_tunnel_connect", _WHY_TUNNEL)


COMMUNICATION_HANDLERS: Mapping[str, ToolHandler] = MappingProxyType(
    {
        "synthorg_messages_list": _messages_list,
        "synthorg_messages_get": _messages_get,
        "synthorg_messages_send": _messages_send,
        "synthorg_messages_delete": _messages_delete,
        "synthorg_meetings_list": _meetings_list,
        "synthorg_meetings_get": _meetings_get,
        "synthorg_meetings_create": _meetings_create,
        "synthorg_meetings_update": _meetings_update,
        "synthorg_meetings_delete": _meetings_delete,
        "synthorg_connections_list": _connections_list,
        "synthorg_connections_get": _connections_get,
        "synthorg_connections_create": _connections_create,
        "synthorg_connections_delete": _connections_delete,
        "synthorg_connections_check_health": _connections_check_health,
        "synthorg_webhooks_list": _webhooks_list,
        "synthorg_webhooks_get": _webhooks_get,
        "synthorg_webhooks_create": _webhooks_create,
        "synthorg_webhooks_update": _webhooks_update,
        "synthorg_webhooks_delete": _webhooks_delete,
        "synthorg_tunnel_get_status": _tunnel_get_status,
        "synthorg_tunnel_connect": _tunnel_connect,
    },
)
