"""WebSocket handler for real-time event feeds.

Clients connect to ``/api/v1/ws?ticket=<ticket>`` and send JSON
messages to subscribe/unsubscribe from named channels with optional
payload filters.  The server pushes ``WsEvent`` JSON on subscribed
channels.

Authentication uses a one-time ticket obtained from
``POST /api/v1/auth/ws-ticket``.  The ticket is validated and
consumed (single-use) before the connection is accepted.
"""

import json
from typing import Any

from litestar import WebSocket  # noqa: TC002
from litestar.channels import ChannelsPlugin
from litestar.exceptions import WebSocketDisconnect
from litestar.handlers import websocket

from synthorg.api.auth.models import AuthenticatedUser  # noqa: TC001
from synthorg.api.channels import ALL_CHANNELS
from synthorg.api.guards import _READ_ROLES, HumanRole
from synthorg.observability import get_logger
from synthorg.observability.events.api import (
    API_WS_AUTH_STAGE,
    API_WS_CONNECTED,
    API_WS_DISCONNECTED,
    API_WS_INVALID_MESSAGE,
    API_WS_SEND_FAILED,
    API_WS_SUBSCRIBE,
    API_WS_TICKET_INVALID,
    API_WS_TRANSPORT_ERROR,
    API_WS_UNKNOWN_ACTION,
    API_WS_UNSUBSCRIBE,
)

logger = get_logger(__name__)

_ALL_CHANNELS_SET: frozenset[str] = frozenset(ALL_CHANNELS)
_MAX_FILTER_KEYS: int = 10
_MAX_FILTER_VALUE_LEN: int = 256
_MAX_WS_MESSAGE_BYTES: int = 4096

# Application-layer WS close codes (RFC 6455 §7.4.2: 4000-4999).
_WS_CLOSE_AUTH_FAILED: int = 4001
_WS_CLOSE_FORBIDDEN: int = 4003


async def _validate_ticket(
    socket: WebSocket[Any, Any, Any],
) -> AuthenticatedUser | None:
    """Validate the one-time ticket and return the user.

    Returns ``None`` and closes the socket if the ticket is
    missing, invalid, or expired.
    """
    ticket = socket.query_params.get("ticket")
    logger.debug(
        API_WS_AUTH_STAGE,
        stage="ticket_check",
        has_ticket=bool(ticket),
        client=str(socket.client),
    )
    if not ticket:
        logger.warning(API_WS_TICKET_INVALID, reason="missing_ticket")
        await socket.close(code=_WS_CLOSE_AUTH_FAILED, reason="Missing ticket")
        return None

    app_state = socket.app.state["app_state"]
    user: AuthenticatedUser | None = app_state.ticket_store.validate_and_consume(
        ticket,
    )
    if user is None:
        logger.warning(
            API_WS_TICKET_INVALID,
            reason="invalid_or_expired",
            client=str(socket.client),
        )
        await socket.close(
            code=_WS_CLOSE_AUTH_FAILED,
            reason="Invalid or expired ticket",
        )
        return None

    logger.debug(
        API_WS_AUTH_STAGE,
        stage="ticket_valid",
        user_id=user.user_id,
    )
    return user


async def _check_ws_role(
    socket: WebSocket[Any, Any, Any],
    user: AuthenticatedUser,
) -> bool:
    """Verify the user has a role permitted for WebSocket access.

    Returns ``True`` if the role is valid.  On failure, closes the
    socket with a forbidden code and returns ``False``.
    """
    logger.debug(
        API_WS_AUTH_STAGE,
        stage="role_check",
        user_id=user.user_id,
        role=str(user.role),
    )
    # Defense-in-depth: user.role is already validated as HumanRole by
    # Pydantic, and _READ_ROLES == frozenset(HumanRole).  These checks
    # guard against future changes to the role model or read-role set.
    try:
        role = HumanRole(user.role)
    except ValueError:
        logger.warning(
            API_WS_TICKET_INVALID,
            reason="invalid_role",
            role=str(user.role),
        )
        await socket.close(code=_WS_CLOSE_FORBIDDEN, reason="Invalid role")
        return False

    if role not in _READ_ROLES:
        logger.warning(
            API_WS_TICKET_INVALID,
            reason="insufficient_role",
            role=role.value,
        )
        await socket.close(
            code=_WS_CLOSE_FORBIDDEN,
            reason="Insufficient permissions",
        )
        return False

    return True


async def _on_event(
    event_data: bytes,
    subscribed: set[str],
    filters: dict[str, dict[str, str]],
    socket: WebSocket[Any, Any, Any],
) -> None:
    """Filter and forward a single channel event to the client."""
    try:
        event = json.loads(event_data)
    except json.JSONDecodeError:
        logger.warning(
            API_WS_INVALID_MESSAGE,
            data_preview=str(event_data)[:100],
            source="channels_backend",
        )
        return
    except TypeError:
        logger.error(
            API_WS_INVALID_MESSAGE,
            data_type=type(event_data).__name__,
            reason="unexpected_type",
            source="channels_backend",
            exc_info=True,
        )
        return

    if not isinstance(event, dict):
        logger.warning(
            API_WS_INVALID_MESSAGE,
            data_preview=str(event_data)[:100],
            reason="not_a_dict",
        )
        return

    channel = event.get("channel", "")
    if channel not in subscribed:
        return

    channel_filters = filters.get(channel)
    if channel_filters:
        payload = event.get("payload", {})
        if not isinstance(payload, dict):
            return
        if not all(payload.get(k) == v for k, v in channel_filters.items()):
            return

    try:
        await socket.send_text(event_data.decode("utf-8"))
    except WebSocketDisconnect:
        logger.debug(API_WS_SEND_FAILED, reason="client_disconnected")
    except Exception:
        logger.warning(API_WS_SEND_FAILED, exc_info=True)
        await socket.close(code=1011, reason="Internal error")


# Defense-in-depth: opt signals Litestar's auth middleware to skip
# this handler.  The middleware is already HTTP-only (ScopeType.HTTP)
# and the WS path is regex-excluded, so this is a tertiary safeguard.
@websocket("/ws", opt={"exclude_from_auth": True})
async def ws_handler(
    socket: WebSocket[Any, Any, Any],
) -> None:
    """Handle WebSocket connections with channel subscriptions.

    Authentication is performed via a one-time ticket passed as
    ``?ticket=<ticket>`` in the query string.  The ticket is
    validated and consumed before the connection is accepted.

    Protocol (JSON from client):
        ``{"action": "subscribe", "channels": ["tasks"],
          "filters": {"agent_id": "...", "project": "..."}}``
        ``{"action": "unsubscribe", "channels": ["tasks"]}``
    """
    user = await _validate_ticket(socket)
    if user is None:
        return

    if not await _check_ws_role(socket, user):
        return

    # Resolve ChannelsPlugin by iterating app.plugins -- the same
    # pattern used by get_channels_plugin() in channels.py.
    # Litestar's DI does not reliably inject plugin instances into
    # WebSocket handlers (the parameter is misidentified as a query
    # param, causing a Litestar-internal 4500 close before the
    # handler runs).  See #549.
    channels_plugin: ChannelsPlugin | None = None
    for plugin in socket.app.plugins:
        if isinstance(plugin, ChannelsPlugin):
            channels_plugin = plugin
            break
    if channels_plugin is None:
        logger.warning(
            API_WS_SEND_FAILED,
            reason="channels_plugin_not_registered",
        )
        await socket.close(code=1011, reason="Internal error")
        return

    try:
        subscriber = await channels_plugin.subscribe(list(ALL_CHANNELS))
    except Exception:
        logger.warning(
            API_WS_SEND_FAILED,
            reason="subscribe_failed",
            client=str(socket.client),
            user_id=user.user_id,
            exc_info=True,
        )
        await socket.close(code=1011, reason="Internal error")
        return

    # Accept only after auth, role check, plugin resolution, and
    # subscription all succeed -- avoid accepting then immediately
    # closing on infrastructure failures.
    socket.scope["user"] = user
    await socket.accept()
    logger.info(
        API_WS_CONNECTED,
        client=str(socket.client),
        user_id=user.user_id,
    )

    subscribed: set[str] = set()
    filters: dict[str, dict[str, str]] = {}

    async def _event_callback(event_data: bytes) -> None:
        await _on_event(event_data, subscribed, filters, socket)

    try:
        async with subscriber.run_in_background(_event_callback):
            await _receive_loop(socket, subscribed, filters)
    finally:
        await channels_plugin.unsubscribe(subscriber)
        logger.info(API_WS_DISCONNECTED, client=str(socket.client))


async def _receive_loop(
    socket: WebSocket[Any, Any, Any],
    subscribed: set[str],
    filters: dict[str, dict[str, str]],
) -> None:
    """Process client subscribe/unsubscribe commands."""
    try:
        while True:
            data = await socket.receive_text()
            response = _handle_message(data, subscribed, filters)
            await socket.send_text(response)
    except WebSocketDisconnect:
        logger.debug(API_WS_DISCONNECTED, reason="client_disconnect")
    except Exception:
        user = socket.scope.get("user")
        logger.error(
            API_WS_TRANSPORT_ERROR,
            user_id=getattr(user, "user_id", "unknown"),
            client=str(socket.client),
            exc_info=True,
        )
        raise


def _parse_ws_message(
    data: str,
) -> dict[str, Any] | str:
    """Parse raw JSON from the client, returning a dict or an error string."""
    if len(data.encode()) > _MAX_WS_MESSAGE_BYTES:
        return json.dumps({"error": "Message too large"})

    try:
        msg = json.loads(data)
    except json.JSONDecodeError:
        logger.warning(API_WS_INVALID_MESSAGE, data_preview=str(data)[:100])
        return json.dumps({"error": "Invalid JSON"})
    except TypeError:
        logger.error(
            API_WS_INVALID_MESSAGE,
            data_type=type(data).__name__,
            reason="unexpected_type",
            exc_info=True,
        )
        return json.dumps({"error": "Invalid JSON"})

    if not isinstance(msg, dict):
        return json.dumps({"error": "Expected JSON object"})

    return msg


def _validate_ws_fields(
    msg: dict[str, Any],
) -> tuple[str, list[str], dict[str, Any] | None] | str:
    """Extract and validate action, channels, and filters from a parsed message.

    Returns ``(action, channels, client_filters)`` on success, or a
    JSON error string on validation failure.
    """
    action = str(msg.get("action", ""))
    channels = msg.get("channels", [])
    # None = key absent (leave existing filters), {} = explicitly clear
    raw_filters = msg.get("filters")
    client_filters: dict[str, Any] | None = None
    if raw_filters is not None:
        if not isinstance(raw_filters, dict):
            return json.dumps({"error": "filters must be an object"})
        client_filters = raw_filters

    if not isinstance(channels, list) or not all(isinstance(c, str) for c in channels):
        return json.dumps({"error": "channels must be a list of strings"})

    return (action, channels, client_filters)


def _handle_message(
    data: str,
    subscribed: set[str],
    filters: dict[str, dict[str, str]],
) -> str:
    """Parse, validate, and dispatch a single client message."""
    parsed = _parse_ws_message(data)
    if isinstance(parsed, str):
        return parsed

    fields = _validate_ws_fields(parsed)
    if isinstance(fields, str):
        return fields

    action, channels, client_filters = fields

    if action == "subscribe":
        return _handle_subscribe(channels, client_filters, subscribed, filters)

    if action == "unsubscribe":
        return _handle_unsubscribe(channels, subscribed, filters)

    logger.warning(API_WS_UNKNOWN_ACTION, action=str(action)[:64])
    return json.dumps({"error": "Unknown action"})


def _handle_subscribe(
    channels: list[str],
    client_filters: dict[str, Any] | None,
    subscribed: set[str],
    filters: dict[str, dict[str, str]],
) -> str:
    """Process a subscribe action.

    Filter semantics:
        ``None``  — filters key absent, leave existing filters unchanged.
        ``{}``    — explicitly clear filters for the subscribed channels.
        ``{...}`` — set new filters for the subscribed channels.
    """
    if client_filters is not None and (
        len(client_filters) > _MAX_FILTER_KEYS
        or any(len(str(v)) > _MAX_FILTER_VALUE_LEN for v in client_filters.values())
    ):
        return json.dumps({"error": "Filter bounds exceeded"})

    valid = [c for c in channels if c in _ALL_CHANNELS_SET]
    subscribed.update(valid)
    if client_filters is not None:
        for c in valid:
            if client_filters:
                filters[c] = dict(client_filters)
            else:
                filters.pop(c, None)
    logger.debug(
        API_WS_SUBSCRIBE,
        channels=valid,
        active=sorted(subscribed),
    )
    return json.dumps({"action": "subscribed", "channels": sorted(subscribed)})


def _handle_unsubscribe(
    channels: list[str],
    subscribed: set[str],
    filters: dict[str, dict[str, str]],
) -> str:
    """Process an unsubscribe action."""
    subscribed -= set(channels)
    for c in channels:
        filters.pop(c, None)
    logger.debug(
        API_WS_UNSUBSCRIBE,
        channels=channels,
        active=sorted(subscribed),
    )
    return json.dumps({"action": "unsubscribed", "channels": sorted(subscribed)})
