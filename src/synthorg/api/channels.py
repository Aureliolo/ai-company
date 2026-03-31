"""WebSocket channel constants, plugin factory, and shared publish helper.

Defines the named channels for real-time event feeds and
creates the Litestar ``ChannelsPlugin`` with an in-memory backend.
"""

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Final

from litestar.channels import ChannelsPlugin
from litestar.channels.backends.memory import MemoryChannelsBackend

from synthorg.api.ws_models import WsEvent, WsEventType
from synthorg.observability import get_logger
from synthorg.observability.events.api import API_WS_SEND_FAILED

if TYPE_CHECKING:
    from litestar import Request

logger = get_logger(__name__)

CHANNEL_TASKS: Final[str] = "tasks"
CHANNEL_AGENTS: Final[str] = "agents"
CHANNEL_BUDGET: Final[str] = "budget"
CHANNEL_MESSAGES: Final[str] = "messages"
CHANNEL_SYSTEM: Final[str] = "system"
CHANNEL_APPROVALS: Final[str] = "approvals"
CHANNEL_MEETINGS: Final[str] = "meetings"
CHANNEL_ARTIFACTS: Final[str] = "artifacts"
CHANNEL_PROJECTS: Final[str] = "projects"

ALL_CHANNELS: Final[tuple[str, ...]] = (
    CHANNEL_TASKS,
    CHANNEL_AGENTS,
    CHANNEL_BUDGET,
    CHANNEL_MESSAGES,
    CHANNEL_SYSTEM,
    CHANNEL_APPROVALS,
    CHANNEL_MEETINGS,
    CHANNEL_ARTIFACTS,
    CHANNEL_PROJECTS,
)


def get_channels_plugin(
    request: Request[Any, Any, Any],
) -> ChannelsPlugin | None:
    """Extract the ``ChannelsPlugin`` from the application, or ``None``.

    Args:
        request: The incoming Litestar request.

    Returns:
        The ``ChannelsPlugin`` instance if registered, otherwise ``None``.
    """
    for plugin in request.app.plugins:
        if isinstance(plugin, ChannelsPlugin):
            return plugin
    return None


def publish_ws_event(
    request: Request[Any, Any, Any],
    event_type: WsEventType,
    channel: str,
    payload: dict[str, object],
) -> None:
    """Best-effort publish an event to a named WebSocket channel.

    Logs a warning and returns silently if the ``ChannelsPlugin``
    is not registered or the publish call fails.  ``MemoryError``
    and ``RecursionError`` are always re-raised.

    Args:
        request: The incoming Litestar request.
        event_type: Classification of the event.
        channel: Target channel name (must be in ``ALL_CHANNELS``).
        payload: Event-specific data.
    """
    channels_plugin = get_channels_plugin(request)
    if channels_plugin is None:
        logger.warning(
            API_WS_SEND_FAILED,
            note="ChannelsPlugin not available, dropping WS event",
            event_type=event_type.value,
            channel=channel,
        )
        return

    event = WsEvent(
        event_type=event_type,
        channel=channel,
        timestamp=datetime.now(UTC),
        payload=payload,
    )
    try:
        channels_plugin.publish(
            event.model_dump_json(),
            channels=[channel],
        )
    except MemoryError, RecursionError:
        raise
    except Exception:
        logger.warning(
            API_WS_SEND_FAILED,
            event_type=event_type.value,
            channel=channel,
            note="Failed to publish WS event",
            exc_info=True,
        )


def create_channels_plugin() -> ChannelsPlugin:
    """Create the channels plugin with in-memory backend.

    Returns:
        Configured ``ChannelsPlugin`` with 20-message history
        per channel and no arbitrary channel creation.
    """
    return ChannelsPlugin(
        backend=MemoryChannelsBackend(history=20),
        channels=ALL_CHANNELS,
        arbitrary_channels_allowed=False,
    )
