"""Settings change dispatcher — polls ``#settings`` and routes to subscribers.

Follows the same polling-loop pattern as
:class:`~synthorg.api.bus_bridge.MessageBusBridge`.
"""

import asyncio
import contextlib
from typing import TYPE_CHECKING, Final

from synthorg.communication.bus_protocol import MessageBus  # noqa: TC001
from synthorg.communication.channel import Channel
from synthorg.communication.enums import ChannelType
from synthorg.communication.errors import ChannelAlreadyExistsError
from synthorg.observability import get_logger

if TYPE_CHECKING:
    from synthorg.communication.message import Message
from synthorg.observability.events.settings import (
    SETTINGS_CHANNEL_CREATED,
    SETTINGS_DISPATCHER_CHANNEL_DEAD,
    SETTINGS_DISPATCHER_POLL_ERROR,
    SETTINGS_DISPATCHER_STARTED,
    SETTINGS_DISPATCHER_STOPPED,
    SETTINGS_SUBSCRIBER_ERROR,
    SETTINGS_SUBSCRIBER_NOTIFIED,
    SETTINGS_SUBSCRIBER_RESTART_REQUIRED,
)
from synthorg.settings.subscriber import SettingsSubscriber  # noqa: TC001

logger = get_logger(__name__)

_SUBSCRIBER_ID: Final[str] = "__settings_dispatcher__"
_POLL_TIMEOUT: Final[float] = 1.0
_MAX_CONSECUTIVE_ERRORS: Final[int] = 30
_SETTINGS_CHANNEL: Final[str] = "#settings"


class SettingsChangeDispatcher:
    """Dispatch ``#settings`` bus messages to registered subscribers.

    On ``start()``, subscribes to the ``#settings`` channel and
    begins polling for change notifications published by
    :class:`~synthorg.settings.service.SettingsService`.

    Each incoming message is matched against subscribers'
    ``watched_keys``.  For settings with ``restart_required=True``,
    a WARNING is logged and subscribers are **not** called.  For all
    other settings, matching subscribers' ``on_settings_changed``
    is invoked.  Errors in individual subscribers are logged and
    swallowed — the poll loop is never interrupted.

    Args:
        message_bus: The message bus to poll.
        subscribers: Registered settings subscribers.
    """

    def __init__(
        self,
        message_bus: MessageBus,
        subscribers: tuple[SettingsSubscriber, ...],
    ) -> None:
        self._bus = message_bus
        self._subscribers = subscribers
        self._task: asyncio.Task[None] | None = None
        self._running: bool = False

    async def start(self) -> None:
        """Start the polling loop.

        Raises:
            RuntimeError: If the dispatcher is already running.
        """
        if self._running:
            msg = "SettingsChangeDispatcher is already running"
            raise RuntimeError(msg)

        await self._ensure_channel()
        await self._bus.subscribe(_SETTINGS_CHANNEL, _SUBSCRIBER_ID)

        self._running = True
        self._task = asyncio.create_task(
            self._poll_loop(),
            name="settings-dispatcher",
        )
        logger.info(
            SETTINGS_DISPATCHER_STARTED,
            subscriber_count=len(self._subscribers),
        )

    async def stop(self) -> None:
        """Cancel the polling task.  Idempotent."""
        if not self._running:
            return

        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None

        self._running = False
        logger.info(SETTINGS_DISPATCHER_STOPPED)

    async def _ensure_channel(self) -> None:
        """Create ``#settings`` channel if it does not exist."""
        try:
            await self._bus.create_channel(
                Channel(name=_SETTINGS_CHANNEL, type=ChannelType.TOPIC),
            )
            logger.debug(SETTINGS_CHANNEL_CREATED, channel=_SETTINGS_CHANNEL)
        except ChannelAlreadyExistsError:
            pass

    async def _poll_loop(self) -> None:
        """Continuously poll ``#settings`` and dispatch to subscribers."""
        consecutive_errors = 0

        while True:
            try:
                envelope = await self._bus.receive(
                    _SETTINGS_CHANNEL,
                    _SUBSCRIBER_ID,
                    timeout=_POLL_TIMEOUT,
                )
                if envelope is None:
                    continue
                consecutive_errors = 0
                await self._dispatch(envelope.message)
            except asyncio.CancelledError:
                break
            except MemoryError, RecursionError:
                raise
            except OSError, ConnectionError, TimeoutError:
                consecutive_errors += 1
                if consecutive_errors >= _MAX_CONSECUTIVE_ERRORS:
                    logger.exception(
                        SETTINGS_DISPATCHER_CHANNEL_DEAD,
                        consecutive_errors=consecutive_errors,
                    )
                    break
                logger.warning(
                    SETTINGS_DISPATCHER_POLL_ERROR,
                    consecutive_errors=consecutive_errors,
                    exc_info=True,
                )
                await asyncio.sleep(_POLL_TIMEOUT)
            except Exception:
                logger.error(
                    SETTINGS_DISPATCHER_CHANNEL_DEAD,
                    exc_info=True,
                )
                break

    async def _dispatch(self, message: Message) -> None:
        """Route a single settings change to matching subscribers."""
        meta = _extract_metadata(message)
        if meta is None:
            return

        namespace, key, restart_required = meta

        if restart_required:
            logger.warning(
                SETTINGS_SUBSCRIBER_RESTART_REQUIRED,
                namespace=namespace,
                key=key,
            )
            return

        for subscriber in self._subscribers:
            if (namespace, key) not in subscriber.watched_keys:
                continue
            try:
                await subscriber.on_settings_changed(namespace, key)
                logger.info(
                    SETTINGS_SUBSCRIBER_NOTIFIED,
                    subscriber=subscriber.subscriber_name,
                    namespace=namespace,
                    key=key,
                )
            except MemoryError, RecursionError:
                raise
            except Exception:
                logger.error(
                    SETTINGS_SUBSCRIBER_ERROR,
                    subscriber=subscriber.subscriber_name,
                    namespace=namespace,
                    key=key,
                    exc_info=True,
                )


def _extract_metadata(
    message: Message,
) -> tuple[str, str, bool] | None:
    """Extract (namespace, key, restart_required) from message metadata.

    Returns:
        A tuple of (namespace, key, restart_required) or ``None`` if
        the required metadata fields are missing.
    """
    extra = dict(message.metadata.extra)
    namespace = extra.get("namespace")
    key = extra.get("key")
    if namespace is None or key is None:
        return None
    restart_required = extra.get("restart_required", "False").lower() == "true"
    return namespace, key, restart_required
