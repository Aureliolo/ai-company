"""NATS JetStream message bus backend.

Thin facade over focused submodules. Delegates all logic to:

- ``_nats_connection``: connect, drain, stream/KV setup, stop
- ``_nats_channels``: channel creation, resolution, listing, subjects
- ``_nats_consumers``: subscribe, unsubscribe, pull consumer lifecycle
- ``_nats_kv``: KV bucket read/write/scan
- ``_nats_publish``: publish, send_direct, serialization
- ``_nats_receive``: receive loop, fetch, ack, envelope building
- ``_nats_history``: history scanning with ephemeral consumers
- ``_nats_state``: shared mutable state dataclass
- ``_nats_utils``: pure utilities and constants

See ``docs/design/distributed-runtime.md`` for the full design.

Note: ``nats-py`` is an optional dependency (``pip install
synthorg[distributed]``). Importing this module raises
``ImportError`` if the package is not installed.
"""

from collections.abc import Sequence  # noqa: TC003

from synthorg.communication.bus import _nats_channels as _ch
from synthorg.communication.bus import _nats_connection as _conn
from synthorg.communication.bus import _nats_consumers as _cons
from synthorg.communication.bus import _nats_history as _hist
from synthorg.communication.bus import _nats_publish as _pub
from synthorg.communication.bus import _nats_receive as _recv
from synthorg.communication.bus._nats_state import create_state
from synthorg.communication.bus._nats_utils import require_running
from synthorg.communication.channel import Channel
from synthorg.communication.config import MessageBusConfig  # noqa: TC001
from synthorg.communication.enums import ChannelType
from synthorg.communication.errors import MessageBusAlreadyRunningError
from synthorg.communication.message import Message  # noqa: TC001
from synthorg.communication.subscription import (  # noqa: TC001
    DeliveryEnvelope,
    Subscription,
)
from synthorg.observability import get_logger
from synthorg.observability.events.communication import (
    COMM_BUS_ALREADY_RUNNING,
    COMM_BUS_STARTED,
)

logger = get_logger(__name__)


class JetStreamMessageBus:
    """NATS JetStream-backed message bus.

    Implements the :class:`MessageBus` protocol using durable pull
    consumers as the per-(channel, subscriber) queue primitive.

    Args:
        config: Bus configuration (channels, retention). The
            ``nats`` sub-block must be non-``None``.

    Raises:
        ValueError: If ``config.nats`` is ``None``.
        ImportError: If ``nats-py`` is not installed.
    """

    def __init__(self, *, config: MessageBusConfig) -> None:
        if config.nats is None:
            msg = (
                "JetStreamMessageBus requires config.nats to be set. "
                "Provide a NatsConfig in MessageBusConfig.nats."
            )
            raise ValueError(msg)
        try:
            import nats  # noqa: F401,PLC0415
        except ImportError as exc:
            msg = (
                "nats-py is required for the JetStream bus backend. "
                "Install with 'pip install synthorg[distributed]'."
            )
            raise ImportError(msg) from exc
        self._state = create_state(config)

    @property
    def is_running(self) -> bool:
        """Whether the bus is currently running."""
        return self._state.running

    async def start(self) -> None:
        """Connect to NATS, create the stream, and register channels.

        Raises:
            MessageBusAlreadyRunningError: If already running.
            BusConnectionError: If connection to NATS fails.
            BusStreamError: If stream or KV bucket setup fails.
        """
        state = self._state
        async with state.lock:
            if state.running:
                msg = "Message bus is already running"
                logger.warning(COMM_BUS_ALREADY_RUNNING)
                raise MessageBusAlreadyRunningError(msg)

            try:
                await _conn.connect(state)
                await _conn.ensure_stream(state)
                await _conn.ensure_kv_bucket(state)
            except BaseException:
                await _conn.drain_partial_client(state)
                raise

            for name in state.config.channels:
                ch = Channel(name=name, type=ChannelType.TOPIC)
                state.channels[name] = ch

            state.running = True
            state.shutdown_event.clear()

        logger.info(
            COMM_BUS_STARTED,
            channels_created=len(state.config.channels),
            backend="nats",
        )

    async def stop(self) -> None:
        """Stop the bus gracefully. Idempotent."""
        await _conn.stop(self._state)

    async def publish(
        self,
        message: Message,
        *,
        ttl_seconds: float | None = None,
    ) -> None:
        """Publish a message to its channel via JetStream."""
        await _pub.publish(self._state, message, ttl_seconds=ttl_seconds)

    async def send_direct(
        self,
        message: Message,
        *,
        recipient: str,
        ttl_seconds: float | None = None,
    ) -> None:
        """Send a direct message, creating the DIRECT channel lazily."""
        await _pub.send_direct(
            self._state,
            message,
            recipient=recipient,
            ttl_seconds=ttl_seconds,
        )

    async def publish_batch(
        self,
        messages: Sequence[Message],
        *,
        ttl_seconds: float | None = None,
    ) -> None:
        """Publish multiple messages using pipelined async publishes."""
        await _pub.publish_batch(
            self._state,
            messages,
            ttl_seconds=ttl_seconds,
        )

    async def subscribe(
        self,
        channel_name: str,
        subscriber_id: str,
    ) -> Subscription:
        """Subscribe an agent to a channel via a durable pull consumer."""
        return await _cons.subscribe(self._state, channel_name, subscriber_id)

    async def unsubscribe(
        self,
        channel_name: str,
        subscriber_id: str,
    ) -> None:
        """Remove a subscription and tear down the pull consumer."""
        await _cons.unsubscribe(self._state, channel_name, subscriber_id)

    async def receive(
        self,
        channel_name: str,
        subscriber_id: str,
        *,
        timeout: float | None = None,  # noqa: ASYNC109
    ) -> DeliveryEnvelope | None:
        """Receive the next message from the durable consumer."""
        return await _recv.receive(
            self._state,
            channel_name,
            subscriber_id,
            timeout=timeout,
        )

    async def create_channel(self, channel: Channel) -> Channel:
        """Create a new channel."""
        async with self._state.lock:
            require_running(self._state)
        return await _ch.create_channel(self._state, channel)

    async def get_channel(self, channel_name: str) -> Channel:
        """Get a channel by name."""
        return await _ch.resolve_channel_or_raise(self._state, channel_name)

    async def list_channels(self) -> tuple[Channel, ...]:
        """List all channels, including those from peer processes."""
        return await _ch.list_channels(self._state)

    async def get_channel_history(
        self,
        channel_name: str,
        *,
        limit: int | None = None,
    ) -> tuple[Message, ...]:
        """Get message history for a channel."""
        return await _hist.get_channel_history(self._state, channel_name, limit=limit)
