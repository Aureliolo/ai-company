"""Pure WebSocket protocol helpers.

Extracted from ``ws.py`` to keep the main handler focused on the
connection lifecycle. Everything here is a stateless function over
already-validated inputs -- no sockets, no async side effects beyond
emitting a log line. This lets ``ws.py`` import individual hooks
(``_parse_event_payload``, ``_handle_message``, ...) and stay below the
800-line module ceiling the project enforces.
"""

import json
from typing import Any

from synthorg.api.auth.models import AuthenticatedUser  # noqa: TC001
from synthorg.api.channels import (
    ALL_CHANNELS,
    BUDGET_CHANNELS,
    extract_user_id,
    is_user_channel,
    user_channel,
)
from synthorg.api.guards import HumanRole
from synthorg.observability import get_logger
from synthorg.observability.events.api import (
    API_WS_INVALID_MESSAGE,
    API_WS_PING,
    API_WS_SUBSCRIBE,
    API_WS_UNKNOWN_ACTION,
    API_WS_UNSUBSCRIBE,
    API_WS_USER_CHANNEL_DENIED,
)

logger = get_logger(__name__)

_ALL_CHANNELS_SET: frozenset[str] = frozenset(ALL_CHANNELS)
_MAX_FILTER_KEYS: int = 10
_MAX_FILTER_VALUE_LEN: int = 256
# Inbound (client -> server) control-message size cap. Subscribe/unsubscribe
# /auth/ping payloads max out around 3 KiB even at full filter limits, so 4
# KiB is a tight DoS guard with deliberate headroom. Keep this in sync with
# ``WS_MAX_INBOUND_BYTES_DEFAULT`` if/when added to client config.
_MAX_WS_MESSAGE_BYTES: int = 4096


def matches_filters(
    event: dict[str, Any],
    channel: str,
    channel_filters: dict[str, str],
) -> bool:
    """Check whether the event payload matches the active channel filters.

    A filter key absent from the payload is a mismatch. ``payload.get``
    returns ``None`` for a missing key, so comparing directly against
    the filter value would incorrectly let clients widen subscriptions
    by sending ``{"task_id": null}`` as the filter: payloads without
    that key would match. Use explicit ``in``-checks instead so a
    missing payload key always fails the filter.
    """
    payload = event.get("payload", {})
    if not isinstance(payload, dict):
        logger.warning(
            API_WS_INVALID_MESSAGE,
            channel=channel,
            reason="payload_not_dict",
            payload_type=type(payload).__name__,
        )
        return False
    for key, expected in channel_filters.items():
        if key not in payload:
            return False
        if payload[key] != expected:
            return False
    return True


def channel_allowed(
    channel: str,
    conn_user: AuthenticatedUser,
) -> bool:
    """Check whether the connected user may receive this channel.

    Server-side access control:
    - User channels: only the owning user.
    - Budget channels: CEO or Manager only.
    - All others: any read-capable user.
    """
    if is_user_channel(channel):
        return extract_user_id(channel) == conn_user.user_id
    if channel in BUDGET_CHANNELS:
        return conn_user.role in (HumanRole.CEO, HumanRole.MANAGER)
    return True


def parse_event_payload(event_data: bytes) -> dict[str, Any] | None:
    """Decode the raw channel payload into a dict, logging+dropping on errors.

    Non-UTF-8 bytes raise ``UnicodeDecodeError`` from the json codec
    before ``json.loads`` ever returns; catch it alongside
    ``JSONDecodeError`` so a single malformed frame is dropped with a
    log rather than crashing the per-client callback.
    """
    try:
        event = json.loads(event_data)
    except json.JSONDecodeError, UnicodeDecodeError:
        logger.warning(
            API_WS_INVALID_MESSAGE,
            data_preview=str(event_data)[:100],
            source="channels_backend",
        )
        return None
    except TypeError:
        logger.error(
            API_WS_INVALID_MESSAGE,
            data_type=type(event_data).__name__,
            reason="unexpected_type",
            source="channels_backend",
            exc_info=True,
        )
        return None

    if not isinstance(event, dict):
        logger.warning(
            API_WS_INVALID_MESSAGE,
            data_preview=str(event_data)[:100],
            reason="not_a_dict",
        )
        return None
    return event


def _parse_ws_message(data: str) -> dict[str, Any] | str:
    """Parse raw JSON from the client, returning a dict or an error string."""
    encoded = data.encode()
    if len(encoded) > _MAX_WS_MESSAGE_BYTES:
        logger.warning(
            API_WS_INVALID_MESSAGE,
            reason="message_too_large",
            size=len(encoded),
        )
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
        logger.warning(
            API_WS_INVALID_MESSAGE,
            reason="not_a_dict",
            message_type=type(msg).__name__,
        )
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
            logger.warning(
                API_WS_INVALID_MESSAGE,
                reason="filters_not_object",
                filters_type=type(raw_filters).__name__,
            )
            return json.dumps({"error": "filters must be an object"})
        # ``filters`` is typed as ``dict[str, str]`` in the server's
        # in-memory subscription map; reject non-string keys/values at
        # the protocol boundary so the wire contract matches the
        # stored shape. Without this a malformed frame like
        # ``{"task_id": null}`` or ``{"task_id": 42}`` would be stored
        # verbatim and could never match any real event.
        if not all(
            isinstance(k, str) and isinstance(v, str) for k, v in raw_filters.items()
        ):
            logger.warning(
                API_WS_INVALID_MESSAGE,
                reason="filters_not_str_to_str",
            )
            return json.dumps(
                {"error": "filters must be an object of string->string"},
            )
        client_filters = raw_filters

    if not isinstance(channels, list) or not all(isinstance(c, str) for c in channels):
        logger.warning(
            API_WS_INVALID_MESSAGE,
            reason="channels_not_list_of_strings",
            channels_type=type(channels).__name__,
        )
        return json.dumps({"error": "channels must be a list of strings"})

    return (action, channels, client_filters)


def handle_message(
    data: str,
    subscribed: set[str],
    filters: dict[str, dict[str, str]],
    conn_user: AuthenticatedUser,
) -> str:
    """Parse, validate, and dispatch a single client message."""
    parsed = _parse_ws_message(data)
    if isinstance(parsed, str):
        return parsed

    # Ping is dispatched before generic field validation because it has
    # no ``channels`` field; running it through ``_validate_ws_fields``
    # would force callers to send a meaningless empty array.
    if isinstance(parsed, dict) and parsed.get("action") == "ping":
        logger.debug(API_WS_PING)
        return json.dumps({"action": "pong"})

    fields = _validate_ws_fields(parsed)
    if isinstance(fields, str):
        return fields

    action, channels, client_filters = fields

    if action == "subscribe":
        return _handle_subscribe(
            channels,
            client_filters,
            subscribed,
            filters,
            conn_user,
        )

    if action == "unsubscribe":
        return _handle_unsubscribe(channels, subscribed, filters)

    logger.warning(API_WS_UNKNOWN_ACTION, action=str(action)[:64])
    return json.dumps({"error": "Unknown action"})


def _handle_subscribe(
    channels: list[str],
    client_filters: dict[str, Any] | None,
    subscribed: set[str],
    filters: dict[str, dict[str, str]],
    conn_user: AuthenticatedUser,
) -> str:
    """Process a subscribe action.

    Filter semantics:
        ``None``  -- filters key absent, leave existing filters unchanged.
        ``{}``    -- explicitly clear filters for the subscribed channels.
        ``{...}`` -- set new filters for the subscribed channels.
    """
    if client_filters is not None and (
        len(client_filters) > _MAX_FILTER_KEYS
        or any(len(str(v)) > _MAX_FILTER_VALUE_LEN for v in client_filters.values())
    ):
        logger.warning(
            API_WS_INVALID_MESSAGE,
            reason="filters_bounds_exceeded",
            filter_count=len(client_filters),
            max_keys=_MAX_FILTER_KEYS,
            max_value_len=_MAX_FILTER_VALUE_LEN,
        )
        return json.dumps({"error": "Filter bounds exceeded"})

    # Accept known channels the user is authorized to receive.
    own_user_ch = user_channel(conn_user.user_id)
    valid: list[str] = []
    for c in channels:
        if c == own_user_ch or (
            c in _ALL_CHANNELS_SET and channel_allowed(c, conn_user)
        ):
            valid.append(c)
        elif is_user_channel(c):
            logger.warning(
                API_WS_USER_CHANNEL_DENIED,
                user_id=conn_user.user_id,
                channel="user:<redacted>",
            )
            # Silently drop -- don't expose other user IDs.
    subscribed.update(valid)
    if client_filters is not None:
        for c in valid:
            if client_filters:
                filters[c] = dict(client_filters)
            else:
                filters.pop(c, None)
    # Subscribe is a state transition ("channel added to active set"),
    # so log at INFO per project logging rules so operators can see
    # per-connection subscription churn in normal dashboards.
    logger.info(
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
    # Mirror subscribe: unsubscribe is also a state transition.
    logger.info(
        API_WS_UNSUBSCRIBE,
        channels=channels,
        active=sorted(subscribed),
    )
    return json.dumps({"action": "unsubscribed", "channels": sorted(subscribed)})
