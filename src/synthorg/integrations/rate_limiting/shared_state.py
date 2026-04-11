"""Bus-coordinated rate limiter shared state.

Enables multi-worker rate limiting by publishing acquire events
to a coordination channel.  Each worker maintains a local sliding
window view of global acquires.

On ``MemoryBus`` (single-worker), the coordination channel is
in-process so the window degrades to local-only -- same code path,
no distributed benefit, minimal overhead.
"""

import asyncio
import contextlib
import time
from collections import deque
from collections.abc import Callable  # noqa: TC003
from datetime import UTC, datetime
from types import MappingProxyType

from synthorg.communication.bus_protocol import MessageBus  # noqa: TC001
from synthorg.communication.channel import Channel
from synthorg.communication.enums import ChannelType, MessageType
from synthorg.communication.message import DataPart, Message
from synthorg.integrations.errors import ConnectionRateLimitError
from synthorg.observability import get_logger
from synthorg.observability.events.integrations import (
    RATE_LIMIT_ACQUIRE_PUBLISHED,
    RATE_LIMIT_COORDINATOR_STARTED,
    RATE_LIMIT_COORDINATOR_STOPPED,
)

logger = get_logger(__name__)

_RATELIMIT_CHANNEL = Channel(name="#ratelimit", type=ChannelType.TOPIC)
_POLL_TIMEOUT = 0.5
_SUBSCRIBER_PREFIX = "__ratelimit_"


class SharedRateLimitCoordinator:
    """Bus-coordinated sliding-window rate limiter.

    Args:
        bus: The message bus instance.
        connection_name: Connection to rate-limit.
        max_rpm: Maximum requests per minute (global across workers).
    """

    def __init__(
        self,
        bus: MessageBus,
        connection_name: str,
        *,
        max_rpm: int = 60,
    ) -> None:
        self._bus = bus
        self._connection_name = connection_name
        self._max_rpm = max_rpm
        self._window: deque[float] = deque()
        self._window_lock = asyncio.Lock()
        self._task: asyncio.Task[None] | None = None
        self._subscriber_id = f"{_SUBSCRIBER_PREFIX}{connection_name}"
        self._started = False

    async def start(self) -> None:
        """Subscribe and start the polling task."""
        if self._started:
            return
        try:
            await self._bus.subscribe(
                _RATELIMIT_CHANNEL.name,
                self._subscriber_id,
            )
        except Exception:
            logger.warning(
                RATE_LIMIT_COORDINATOR_STARTED,
                connection_name=self._connection_name,
                error="subscribe failed, falling back to in-process",
                exc_info=True,
            )
            self._started = True
            return
        self._task = asyncio.create_task(
            self._poll_loop(),
            name=f"ratelimit-{self._connection_name}",
        )
        self._started = True
        logger.debug(
            RATE_LIMIT_COORDINATOR_STARTED,
            connection_name=self._connection_name,
            max_rpm=self._max_rpm,
        )

    async def stop(self) -> None:
        """Cancel polling and unsubscribe."""
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        with contextlib.suppress(Exception):
            await self._bus.unsubscribe(
                _RATELIMIT_CHANNEL.name,
                self._subscriber_id,
            )
        self._started = False
        logger.debug(
            RATE_LIMIT_COORDINATOR_STOPPED,
            connection_name=self._connection_name,
        )

    async def acquire(self) -> None:
        """Acquire a rate limit slot, publish, and check the window.

        Raises:
            ConnectionRateLimitError: If the sliding window is full.
        """
        if not self._started:
            await self.start()

        async with self._window_lock:
            now = time.monotonic()
            self._evict_old(now)

            if len(self._window) >= self._max_rpm:
                msg = (
                    f"Rate limit exceeded for connection "
                    f"'{self._connection_name}' ({self._max_rpm} rpm)"
                )
                raise ConnectionRateLimitError(msg)

            self._window.append(now)
        await self._publish_acquire()

    def _evict_old(self, now: float) -> None:
        """Remove entries older than 60 seconds."""
        cutoff = now - 60.0
        while self._window and self._window[0] < cutoff:
            self._window.popleft()

    async def _publish_acquire(self) -> None:
        """Publish an acquire event for other workers."""
        message = Message(
            timestamp=datetime.now(UTC),
            sender=f"ratelimit:{self._connection_name}",
            to=_RATELIMIT_CHANNEL.name,
            type=MessageType.ANNOUNCEMENT,
            channel=_RATELIMIT_CHANNEL.name,
            parts=(
                DataPart(
                    data=MappingProxyType(
                        {
                            "connection_name": self._connection_name,
                            "timestamp": time.monotonic(),
                        }
                    ),
                ),
            ),
        )
        try:
            await self._bus.publish(message)
            logger.debug(
                RATE_LIMIT_ACQUIRE_PUBLISHED,
                connection_name=self._connection_name,
            )
        except Exception:
            logger.warning(
                RATE_LIMIT_ACQUIRE_PUBLISHED,
                connection_name=self._connection_name,
                error="bus publish failed, falling back to local-only",
                exc_info=True,
            )

    async def _poll_loop(self) -> None:
        """Poll the coordination channel for acquire events."""
        while True:
            try:
                envelope = await self._bus.receive(
                    _RATELIMIT_CHANNEL.name,
                    self._subscriber_id,
                    timeout=_POLL_TIMEOUT,
                )
                if envelope is None:
                    continue
                await self._ingest(envelope.message)
            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(1.0)

    async def _ingest(self, message: object) -> None:
        """Update local window from a remote acquire event."""
        from synthorg.communication.message import (  # noqa: PLC0415
            Message as Msg,
        )

        if not isinstance(message, Msg):
            return
        for part in message.parts:
            if not isinstance(part, DataPart):
                continue
            data = dict(part.data) if part.data is not None else {}
            if data.get("connection_name") != self._connection_name:
                continue
            ts = data.get("timestamp")
            if isinstance(ts, int | float):
                async with self._window_lock:
                    self._window.append(float(ts))
                    self._evict_old(time.monotonic())


_coordinator_factory: Callable[[str], SharedRateLimitCoordinator] | None = None
_coordinators: dict[str, SharedRateLimitCoordinator] = {}


def set_coordinator_factory(
    factory: Callable[[str], SharedRateLimitCoordinator],
) -> None:
    """Set the factory used by the decorator to create coordinators.

    Called from ``auto_wire.py`` after the bus and catalog exist.
    """
    global _coordinator_factory  # noqa: PLW0603
    _coordinator_factory = factory


def get_coordinator(connection_name: str) -> SharedRateLimitCoordinator | None:
    """Get or create a coordinator for the given connection."""
    if _coordinator_factory is None:
        return None
    if connection_name not in _coordinators:
        _coordinators[connection_name] = _coordinator_factory(connection_name)
    return _coordinators[connection_name]
