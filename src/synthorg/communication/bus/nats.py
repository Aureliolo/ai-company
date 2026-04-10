"""NATS JetStream message bus backend.

First distributed :class:`MessageBus` backend for SynthOrg. Maps the
pull-model protocol in ``bus_protocol.py`` onto JetStream primitives:

- A single stream ``<prefix>_BUS`` with ``LimitsPolicy`` retention and
  ``MaxMsgsPerSubject = config.retention.max_messages_per_channel``
  preserves the bounded-history semantic natively.
- Each ``(channel_name, subscriber_id)`` pair maps to a durable pull
  consumer. ``receive(timeout=t)`` becomes
  ``consumer.fetch(batch=1, timeout=t)``.
- Lazily-created DIRECT channels are registered in a JetStream KV
  bucket so they are discoverable across processes.
- Ack is immediate on successful fetch, matching in-memory
  "dequeue-and-go" semantics.

See ``docs/design/distributed-runtime.md`` for the full design.

Note: ``nats-py`` is an optional dependency (``pip install
synthorg[distributed]``). Importing this module raises
``ImportError`` if the package is not installed.
"""

import asyncio
import base64
import json
import time
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Final, NoReturn
from urllib.parse import urlparse

from synthorg.communication.bus.errors import (
    BusConnectionError,
    BusStreamError,
)
from synthorg.communication.channel import Channel
from synthorg.communication.config import (  # noqa: TC001
    MessageBusConfig,
    NatsConfig,
)
from synthorg.communication.enums import ChannelType
from synthorg.communication.errors import (
    ChannelAlreadyExistsError,
    ChannelNotFoundError,
    MessageBusAlreadyRunningError,
    MessageBusNotRunningError,
    NotSubscribedError,
)
from synthorg.communication.message import Message
from synthorg.communication.subscription import (
    DeliveryEnvelope,
    Subscription,
)
from synthorg.observability import get_logger
from synthorg.observability.events.communication import (
    COMM_BUS_ALREADY_RUNNING,
    COMM_BUS_CONNECTED,
    COMM_BUS_DISCONNECTED,
    COMM_BUS_KV_READ_FAILED,
    COMM_BUS_KV_WRITE_FAILED,
    COMM_BUS_MESSAGE_DESERIALIZE_FAILED,
    COMM_BUS_MESSAGE_TOO_LARGE,
    COMM_BUS_NOT_RUNNING,
    COMM_BUS_RECEIVE_ERROR,
    COMM_BUS_RECONNECTING,
    COMM_BUS_STARTED,
    COMM_BUS_STOPPED,
    COMM_BUS_STREAM_SCAN_FAILED,
    COMM_CHANNEL_ALREADY_EXISTS,
    COMM_CHANNEL_CREATED,
    COMM_CHANNEL_NOT_FOUND,
    COMM_DIRECT_SENT,
    COMM_HISTORY_QUERIED,
    COMM_MESSAGE_DELIVERED,
    COMM_MESSAGE_PUBLISHED,
    COMM_RECEIVE_SHUTDOWN,
    COMM_SEND_DIRECT_INVALID,
    COMM_SUBSCRIPTION_CREATED,
    COMM_SUBSCRIPTION_NOT_FOUND,
    COMM_SUBSCRIPTION_REMOVED,
)

if TYPE_CHECKING:
    from nats.aio.client import Client as NatsClient
    from nats.js import JetStreamContext
    from nats.js.kv import KeyValue

logger = get_logger(__name__)

_DM_SEPARATOR = ":"
"""Separator used in deterministic direct-channel names (matches in-memory)."""

_SUBJECT_CHANNEL_TOKEN: Final[str] = "channel"  # noqa: S105
_SUBJECT_DIRECT_TOKEN: Final[str] = "direct"  # noqa: S105

_MAX_BUS_PAYLOAD_BYTES: Final[int] = 4 * 1024 * 1024
"""Maximum bus message payload size (4 MB) accepted from JetStream.

Messages include parts that can carry text/data blobs, so the limit
is higher than the task-claim limit but still bounded to prevent a
single malformed publisher from exhausting worker memory during
deserialization.
"""

_RECEIVE_POLL_WINDOW_SECONDS: Final[float] = 60.0
"""Maximum seconds a single JetStream fetch waits before looping.

``receive()`` uses this value as the upper bound on a single
``_fetch_with_shutdown`` call. A ``timeout=None`` caller loops over
these polls until a message arrives or the bus shuts down; a
bounded ``timeout`` decrements the remaining budget by this window
each iteration. Keeps per-fetch server-side state bounded while
still matching the in-memory bus's "block indefinitely" contract.
"""

_CONSUMER_ACK_WAIT_MULTIPLIER: Final[float] = 6.0
"""Multiplier on ``publish_ack_wait_seconds`` for per-subscriber consumer ack_wait.

A subscriber's durable pull consumer gets an ack deadline that is
several times longer than the publisher's ack wait: publish acks are a
server-side fire-and-forget acknowledgement, while the subscriber's
ack deadline must span receive + application processing + the
possibility of redelivery before being considered in-flight. The 6x
factor mirrors typical JetStream guidance for interactive workloads
and is surfaced here as a named constant so tests and operators can
reason about it without grepping for a raw literal.
"""


def _redact_url(url: str) -> str:
    """Strip credentials from a NATS URL for safe logging.

    ``nats://user:pass@host:port`` -> ``nats://***@host:port``.
    Non-URL strings pass through unchanged (best effort).
    """
    try:
        parsed = urlparse(url)
    except ValueError:
        return url
    if not parsed.hostname:
        return url
    authority = parsed.hostname
    if parsed.port is not None:
        authority = f"{authority}:{parsed.port}"
    has_creds = parsed.username is not None or parsed.password is not None
    if has_creds:
        authority = f"***@{authority}"
    scheme = parsed.scheme or "nats"
    rest = parsed.path or ""
    return f"{scheme}://{authority}{rest}"


def _raise_channel_not_found(channel_name: str) -> NoReturn:
    """Log and raise :class:`ChannelNotFoundError`."""
    logger.warning(COMM_CHANNEL_NOT_FOUND, channel=channel_name)
    msg = f"Channel not found: {channel_name}"
    raise ChannelNotFoundError(msg, context={"channel": channel_name})


def _raise_not_subscribed(
    channel_name: str,
    subscriber_id: str,
) -> NoReturn:
    """Log and raise :class:`NotSubscribedError`."""
    logger.warning(
        COMM_SUBSCRIPTION_NOT_FOUND,
        channel=channel_name,
        subscriber=subscriber_id,
    )
    msg = f"Not subscribed to {channel_name}"
    raise NotSubscribedError(
        msg,
        context={
            "channel": channel_name,
            "subscriber": subscriber_id,
        },
    )


async def _cancel_if_pending(task: asyncio.Task[Any]) -> None:
    """Cancel a task, await completion, and suppress the expected CancelledError.

    Any exception other than ``CancelledError`` is logged at WARNING
    and re-raised so the caller can decide whether recovery is
    possible. The previous ``contextlib.suppress(Exception)`` masked
    genuine errors like transport failures during in-flight fetches.
    """
    if task.done():
        return
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    except Exception:
        logger.warning(
            COMM_BUS_RECEIVE_ERROR,
            phase="cancel_pending_task",
            task_repr=repr(task),
            exc_info=True,
        )
        raise


def _encode_token(name: str) -> str:
    """Encode an arbitrary string into a NATS-subject-safe token.

    JetStream subject tokens may contain alphanumerics, ``-``, and
    ``_`` but not ``#``, ``@``, ``:``, ``.`` or other separators used
    in SynthOrg channel names. Base32 (lowercase, no padding) gives a
    deterministic, collision-free, case-insensitive encoding using
    only safe characters.
    """
    raw = name.encode("utf-8")
    return base64.b32encode(raw).decode("ascii").rstrip("=").lower()


def _decode_token(token: str) -> str:
    """Reverse of :func:`_encode_token`."""
    padding = "=" * ((-len(token)) % 8)
    raw = base64.b32decode((token.upper() + padding).encode("ascii"))
    return raw.decode("utf-8")


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
        self._config: MessageBusConfig = config
        self._nats_config: NatsConfig = config.nats
        self._lock = asyncio.Lock()
        self._channels: dict[str, Channel] = {}
        self._subscriptions: dict[tuple[str, str], Any] = {}
        self._known_agents: set[str] = set()
        self._in_flight_fetches: set[asyncio.Task[Any]] = set()
        self._running = False
        self._shutdown_event = asyncio.Event()
        self._client: NatsClient | None = None
        self._js: JetStreamContext | None = None
        self._kv: KeyValue | None = None

    @property
    def _stream_name(self) -> str:
        """Name of the bus stream (derived from prefix)."""
        return f"{self._nats_config.stream_name_prefix}_BUS"

    @property
    def _kv_bucket_name(self) -> str:
        """Name of the KV bucket for dynamic channel registration."""
        return f"{self._nats_config.stream_name_prefix}_BUS_CHANNELS"

    @property
    def is_running(self) -> bool:
        """Whether the bus is currently running."""
        return self._running

    async def start(self) -> None:
        """Connect to NATS, create the stream, and register pre-configured channels.

        If stream/KV setup fails after ``_connect()`` succeeds, drain
        the partially-initialised client before the exception
        propagates so the caller does not leak a live NATS connection.

        Raises:
            MessageBusAlreadyRunningError: If already running.
            BusConnectionError: If connection to NATS fails.
            BusStreamError: If stream or KV bucket setup fails.
        """
        async with self._lock:
            if self._running:
                msg = "Message bus is already running"
                logger.warning(COMM_BUS_ALREADY_RUNNING)
                raise MessageBusAlreadyRunningError(msg)

            try:
                await self._connect()
                await self._ensure_stream()
                await self._ensure_kv_bucket()
            except BaseException:
                await self._drain_partial_client()
                raise

            for name in self._config.channels:
                ch = Channel(name=name, type=ChannelType.TOPIC)
                self._channels[name] = ch

            self._running = True
            self._shutdown_event.clear()

        logger.info(
            COMM_BUS_STARTED,
            channels_created=len(self._config.channels),
            backend="nats",
        )

    async def _drain_partial_client(self) -> None:
        """Drain a connected NATS client after a failed ``start()``.

        Called from ``start()`` when the stream or KV bucket setup
        raises. Silently swallows drain errors because a drain failure
        cannot be surfaced to the caller -- the original setup
        exception takes precedence -- and the process is about to
        unwind anyway.
        """
        client = self._client
        if client is None:
            return
        try:
            await client.drain()
        except Exception as exc:
            logger.warning(
                COMM_BUS_DISCONNECTED,
                phase="drain_partial",
                error=str(exc),
            )
        finally:
            self._client = None
            self._js = None
            self._kv = None

    async def _connect(self) -> None:
        """Establish the NATS connection."""
        import nats  # noqa: PLC0415
        from nats.errors import NoServersError  # noqa: PLC0415

        async def on_disconnected() -> None:
            logger.warning(COMM_BUS_DISCONNECTED)

        async def on_reconnected() -> None:
            logger.info(COMM_BUS_CONNECTED, reconnect=True)

        async def on_error(exc: Exception) -> None:
            logger.warning(COMM_BUS_RECONNECTING, error=str(exc))

        try:
            self._client = await nats.connect(
                servers=[self._nats_config.url],
                reconnect_time_wait=self._nats_config.reconnect_time_wait_seconds,
                max_reconnect_attempts=self._nats_config.max_reconnect_attempts,
                connect_timeout=self._nats_config.connect_timeout_seconds,
                user_credentials=self._nats_config.credentials_path,
                disconnected_cb=on_disconnected,
                reconnected_cb=on_reconnected,
                error_cb=on_error,
            )
        except (TimeoutError, NoServersError, OSError) as exc:
            redacted = _redact_url(self._nats_config.url)
            msg = f"Failed to connect to NATS at {redacted}: {exc}"
            logger.exception(COMM_BUS_DISCONNECTED, error=msg, url=redacted)
            raise BusConnectionError(
                msg,
                context={"url": redacted},
            ) from exc

        self._js = self._client.jetstream()
        logger.info(COMM_BUS_CONNECTED, url=_redact_url(self._nats_config.url))

    async def _ensure_stream(self) -> None:
        """Create the bus stream if it does not already exist."""
        from nats.errors import Error as NatsError  # noqa: PLC0415
        from nats.js.api import (  # noqa: PLC0415
            RetentionPolicy,
            StorageType,
            StreamConfig,
        )
        from nats.js.errors import NotFoundError  # noqa: PLC0415

        if self._js is None:
            msg = "JetStream context not initialized"
            raise BusStreamError(msg)

        pfx = self._nats_config.stream_name_prefix.lower()
        stream_config = StreamConfig(
            name=self._stream_name,
            subjects=[
                f"{pfx}.bus.{_SUBJECT_CHANNEL_TOKEN}.>",
                f"{pfx}.bus.{_SUBJECT_DIRECT_TOKEN}.>",
            ],
            retention=RetentionPolicy.LIMITS,
            max_msgs_per_subject=(self._config.retention.max_messages_per_channel),
            storage=StorageType.FILE,
        )
        try:
            try:
                await self._js.stream_info(self._stream_name)
            except NotFoundError:
                await self._js.add_stream(stream_config)
            else:
                await self._js.update_stream(stream_config)
        except NatsError as exc:
            msg = f"Failed to set up stream {self._stream_name}: {exc}"
            logger.warning(
                COMM_BUS_STREAM_SCAN_FAILED,
                stream=self._stream_name,
                error=str(exc),
                phase="ensure_stream",
            )
            raise BusStreamError(
                msg,
                context={"stream": self._stream_name},
            ) from exc

    async def _ensure_kv_bucket(self) -> None:
        """Create the KV bucket for dynamic channel registration."""
        from nats.errors import Error as NatsError  # noqa: PLC0415
        from nats.js.errors import BucketNotFoundError  # noqa: PLC0415

        if self._js is None:
            msg = "JetStream context not initialized"
            raise BusStreamError(msg)

        try:
            try:
                self._kv = await self._js.key_value(self._kv_bucket_name)
            except BucketNotFoundError:
                self._kv = await self._js.create_key_value(
                    bucket=self._kv_bucket_name,
                )
        except NatsError as exc:
            msg = f"Failed to set up KV bucket {self._kv_bucket_name}: {exc}"
            logger.warning(
                COMM_BUS_KV_READ_FAILED,
                channel="*",
                error=str(exc),
                phase="ensure_kv_bucket",
            )
            raise BusStreamError(
                msg,
                context={"bucket": self._kv_bucket_name},
            ) from exc

    async def stop(self) -> None:
        """Stop the bus gracefully. Idempotent.

        Cancels outstanding ``receive()`` calls and closes the
        underlying NATS connection.
        """
        async with self._lock:
            if not self._running:
                return
            self._running = False
        self._shutdown_event.set()

        for task in list(self._in_flight_fetches):
            task.cancel()
        if self._in_flight_fetches:
            await asyncio.gather(
                *self._in_flight_fetches,
                return_exceptions=True,
            )
        self._in_flight_fetches.clear()

        for key, sub in self._subscriptions.items():
            try:
                await sub.unsubscribe()
            except asyncio.CancelledError:
                pass
            except Exception:
                logger.warning(
                    COMM_BUS_DISCONNECTED,
                    phase="stop_unsubscribe",
                    subscription=str(key),
                    exc_info=True,
                )
        self._subscriptions.clear()

        if self._client is not None:
            try:
                await self._client.drain()
            except asyncio.CancelledError:
                pass
            except Exception:
                logger.warning(
                    COMM_BUS_DISCONNECTED,
                    phase="stop_drain",
                    exc_info=True,
                )
            self._client = None
            self._js = None
            self._kv = None

        logger.info(COMM_BUS_STOPPED, backend="nats")

    def _require_running(self) -> None:
        """Raise if the bus is not running."""
        if not self._running:
            logger.warning(COMM_BUS_NOT_RUNNING)
            msg = "Message bus is not running"
            raise MessageBusNotRunningError(msg)

    def _channel_subject(self, channel_name: str) -> str:
        """Compute the stream subject for a TOPIC/BROADCAST channel."""
        pfx = self._nats_config.stream_name_prefix.lower()
        return f"{pfx}.bus.{_SUBJECT_CHANNEL_TOKEN}.{_encode_token(channel_name)}"

    def _direct_subject(self, channel_name: str) -> str:
        """Compute the stream subject for a DIRECT channel."""
        pfx = self._nats_config.stream_name_prefix.lower()
        return f"{pfx}.bus.{_SUBJECT_DIRECT_TOKEN}.{_encode_token(channel_name)}"

    def _subject_for_channel(self, channel: Channel) -> str:
        """Pick the correct subject based on channel type."""
        if channel.type == ChannelType.DIRECT:
            return self._direct_subject(channel.name)
        return self._channel_subject(channel.name)

    @staticmethod
    def _durable_name(channel_name: str, subscriber_id: str) -> str:
        """Compute a safe durable consumer name."""
        return f"{_encode_token(channel_name)}__{_encode_token(subscriber_id)}"

    async def publish(self, message: Message) -> None:
        """Publish a message to its channel via the JetStream stream.

        Uses ``_resolve_channel_or_raise`` so a publisher in a
        different process than the channel creator can publish without
        calling ``get_channel()`` first, matching the multi-process
        contract already established for subscribe/receive/history.

        Args:
            message: The message to publish.

        Raises:
            MessageBusNotRunningError: If not running.
            ChannelNotFoundError: If the channel does not exist.
        """
        async with self._lock:
            self._require_running()
        channel_name = message.channel
        channel = await self._resolve_channel_or_raise(channel_name)
        subject = self._subject_for_channel(channel)

        payload = self._serialize_message(message)
        await self._publish_with_ack(subject, payload)

        logger.info(
            COMM_MESSAGE_PUBLISHED,
            channel=channel_name,
            message_id=str(message.id),
            type=str(message.type),
            backend="nats",
        )

    async def _publish_with_ack(self, subject: str, payload: bytes) -> None:
        """Publish to JetStream waiting for server ack."""
        if self._js is None:
            msg = "JetStream context not initialized"
            raise MessageBusNotRunningError(msg)
        await asyncio.wait_for(
            self._js.publish(subject, payload),
            timeout=self._nats_config.publish_ack_wait_seconds,
        )

    @staticmethod
    def _serialize_message(message: Message) -> bytes:
        """Serialize a Message to JSON bytes for the wire."""
        return message.model_dump_json().encode("utf-8")

    @staticmethod
    def _deserialize_message(data: bytes) -> Message:
        """Reconstruct a Message from wire JSON bytes."""
        return Message.model_validate_json(data.decode("utf-8"))

    async def send_direct(
        self,
        message: Message,
        *,
        recipient: str,
    ) -> None:
        """Send a direct message, creating the DIRECT channel lazily.

        Args:
            message: The message to send.
            recipient: Recipient agent ID.

        Raises:
            MessageBusNotRunningError: If not running.
            ValueError: If recipient does not match ``message.to`` or
                if agent IDs contain the separator character.
        """
        sender = message.sender
        if message.to != recipient:
            msg = f"recipient={recipient!r} does not match message.to={message.to!r}"
            logger.warning(COMM_SEND_DIRECT_INVALID, error=msg)
            raise ValueError(msg)
        for agent_id in (sender, recipient):
            if _DM_SEPARATOR in agent_id:
                msg = (
                    f"Agent ID {agent_id!r} contains the reserved "
                    f"separator character {_DM_SEPARATOR!r}"
                )
                logger.warning(COMM_SEND_DIRECT_INVALID, error=msg)
                raise ValueError(msg)
        a, b = sorted([sender, recipient])
        pair = (a, b)
        channel_name = f"@{pair[0]}:{pair[1]}"

        async with self._lock:
            self._require_running()
            await self._ensure_direct_channel(channel_name, pair)
            self._known_agents.add(sender)
            self._known_agents.add(recipient)

        subject = self._direct_subject(channel_name)
        payload = self._serialize_message(message)
        await self._publish_with_ack(subject, payload)

        logger.info(
            COMM_DIRECT_SENT,
            channel=channel_name,
            sender=sender,
            recipient=recipient,
            message_id=str(message.id),
            backend="nats",
        )

    async def _ensure_direct_channel(
        self,
        channel_name: str,
        pair: tuple[str, str],
    ) -> None:
        """Create DIRECT channel locally and in KV bucket if needed.

        Must be called under ``self._lock``.
        """
        if channel_name in self._channels:
            current = self._channels[channel_name]
            pair_set = set(pair)
            if not pair_set.issubset(set(current.subscribers)):
                new_subs = tuple(sorted(set(current.subscribers) | pair_set))
                self._channels[channel_name] = current.model_copy(
                    update={"subscribers": new_subs},
                )
                await self._write_channel_to_kv(self._channels[channel_name])
            return

        ch = Channel(
            name=channel_name,
            type=ChannelType.DIRECT,
            subscribers=pair,
        )
        self._channels[channel_name] = ch
        await self._write_channel_to_kv(ch)
        logger.info(
            COMM_CHANNEL_CREATED,
            channel=channel_name,
            type=str(ChannelType.DIRECT),
            backend="nats",
        )

    async def _write_channel_to_kv(self, channel: Channel) -> None:
        """Persist a Channel definition to the KV bucket."""
        if self._kv is None:
            return
        key = _encode_token(channel.name)
        value = channel.model_dump_json().encode("utf-8")
        try:
            await self._kv.put(key, value)
        except Exception as exc:
            logger.warning(
                COMM_BUS_KV_WRITE_FAILED,
                channel=channel.name,
                error=str(exc),
            )

    async def _load_channel_from_kv(self, channel_name: str) -> Channel | None:
        """Load a Channel definition from the KV bucket, if present."""
        entry = await self._fetch_kv_entry(channel_name)
        if entry is None:
            return None
        return self._decode_kv_channel(channel_name, entry)

    async def _fetch_kv_entry(self, channel_name: str) -> Any | None:
        """Fetch a raw KV entry, logging transport errors and returning None."""
        from nats.js.errors import KeyNotFoundError  # noqa: PLC0415

        if self._kv is None:
            return None
        key = _encode_token(channel_name)
        try:
            entry = await self._kv.get(key)
        except KeyNotFoundError:
            return None
        except Exception as exc:
            logger.warning(
                COMM_BUS_KV_READ_FAILED,
                channel=channel_name,
                error=str(exc),
            )
            return None
        if entry is None or entry.value is None:
            return None
        return entry

    def _decode_kv_channel(
        self,
        channel_name: str,
        entry: Any,
    ) -> Channel | None:
        """Decode a KV entry into a Channel, logging parse failures."""
        try:
            data = json.loads(entry.value.decode("utf-8"))
            channel = Channel.model_validate(data)
        except json.JSONDecodeError as exc:
            logger.warning(
                COMM_BUS_KV_READ_FAILED,
                channel=channel_name,
                error=str(exc),
            )
            return None
        except ValueError as exc:
            logger.warning(
                COMM_BUS_KV_READ_FAILED,
                channel=channel_name,
                error=str(exc),
            )
            return None
        if channel.name != channel_name:
            logger.warning(
                COMM_BUS_KV_READ_FAILED,
                channel=channel_name,
                error=(
                    f"KV entry name mismatch: expected {channel_name!r}, "
                    f"got {channel.name!r}"
                ),
            )
            return None
        return channel

    async def subscribe(
        self,
        channel_name: str,
        subscriber_id: str,
    ) -> Subscription:
        """Subscribe an agent to a channel via a durable pull consumer.

        Idempotent: returns a fresh Subscription on repeated calls and
        does not recreate the underlying consumer.

        Args:
            channel_name: Channel to subscribe to.
            subscriber_id: Agent ID.

        Returns:
            The subscription record.

        Raises:
            MessageBusNotRunningError: If not running.
            ChannelNotFoundError: If the channel does not exist.
        """
        async with self._lock:
            self._require_running()
        # Resolve through the shared KV-backed resolver so multi-process
        # subscribers can see channels registered by another process.
        await self._resolve_channel_or_raise(channel_name)
        async with self._lock:
            self._require_running()
            channel = self._channels[channel_name]
            self._known_agents.add(subscriber_id)

            key = (channel_name, subscriber_id)
            if key not in self._subscriptions:
                # Create the durable consumer BEFORE mutating the
                # subscriber list so a consumer-creation failure does
                # not leave a ghost subscriber in the cache/KV that
                # no consumer backs.
                await self._create_pull_consumer(
                    channel_name,
                    subscriber_id,
                    channel,
                )

            if subscriber_id not in channel.subscribers:
                new_subs = (*channel.subscribers, subscriber_id)
                updated = channel.model_copy(
                    update={"subscribers": new_subs},
                )
                self._channels[channel_name] = updated
                await self._write_channel_to_kv(updated)

        logger.info(
            COMM_SUBSCRIPTION_CREATED,
            channel=channel_name,
            subscriber=subscriber_id,
            backend="nats",
        )
        return Subscription(
            channel_name=channel_name,
            subscriber_id=subscriber_id,
            subscribed_at=datetime.now(UTC),
        )

    async def _create_pull_consumer(
        self,
        channel_name: str,
        subscriber_id: str,
        channel: Channel,
    ) -> None:
        """Create a durable pull consumer for (channel, subscriber).

        Must be called under ``self._lock``. Passes an explicit
        :class:`ConsumerConfig` so the ack deadline and max-deliver
        semantics documented in the Distributed Runtime design page
        are applied consistently rather than relying on JetStream
        server defaults.
        """
        from nats.js.api import ConsumerConfig  # noqa: PLC0415

        if self._js is None:
            msg = "JetStream context not initialized"
            raise BusStreamError(msg)
        subject = self._subject_for_channel(channel)
        durable = self._durable_name(channel_name, subscriber_id)
        consumer_config = ConsumerConfig(
            durable_name=durable,
            ack_wait=(
                self._nats_config.publish_ack_wait_seconds
                * _CONSUMER_ACK_WAIT_MULTIPLIER
            ),
            max_deliver=1,
            filter_subject=subject,
        )
        sub = await self._js.pull_subscribe(
            subject=subject,
            durable=durable,
            stream=self._stream_name,
            config=consumer_config,
        )
        self._subscriptions[(channel_name, subscriber_id)] = sub

    async def unsubscribe(
        self,
        channel_name: str,
        subscriber_id: str,
    ) -> None:
        """Remove a subscription and tear down the pull consumer.

        Args:
            channel_name: Channel to unsubscribe from.
            subscriber_id: Agent ID.

        Raises:
            MessageBusNotRunningError: If not running.
            NotSubscribedError: If not currently subscribed.
        """
        async with self._lock:
            self._require_running()
            if channel_name not in self._channels:
                _raise_not_subscribed(channel_name, subscriber_id)
            channel = self._channels[channel_name]
            if subscriber_id not in channel.subscribers:
                _raise_not_subscribed(channel_name, subscriber_id)
            new_subs = tuple(s for s in channel.subscribers if s != subscriber_id)
            updated = channel.model_copy(
                update={"subscribers": new_subs},
            )
            self._channels[channel_name] = updated
            await self._write_channel_to_kv(updated)
            key = (channel_name, subscriber_id)
            sub = self._subscriptions.pop(key, None)

        if sub is not None:
            try:
                await sub.unsubscribe()
            except Exception:
                logger.warning(
                    COMM_SUBSCRIPTION_REMOVED,
                    channel=channel_name,
                    subscriber=subscriber_id,
                    backend="nats",
                    phase="unsubscribe_consumer_failed",
                    exc_info=True,
                )

        logger.info(
            COMM_SUBSCRIPTION_REMOVED,
            channel=channel_name,
            subscriber=subscriber_id,
            backend="nats",
        )

    async def receive(
        self,
        channel_name: str,
        subscriber_id: str,
        *,
        timeout: float | None = None,  # noqa: ASYNC109
    ) -> DeliveryEnvelope | None:
        """Receive the next message from the durable consumer.

        Args:
            channel_name: Channel to receive from.
            subscriber_id: Agent ID.
            timeout: Seconds to wait for a message. ``None`` means
                "block indefinitely until a message arrives or the bus
                is shut down", matching the in-memory bus contract;
                a positive value caps the total wait.

        Returns:
            A delivery envelope, or ``None`` on timeout or shutdown.

        Raises:
            MessageBusNotRunningError: If not running.
            ChannelNotFoundError: If the channel does not exist.
            NotSubscribedError: If the subscriber is not subscribed
                (for TOPIC and DIRECT channels).
        """
        sub = await self._resolve_consumer(channel_name, subscriber_id)
        # A single 60s fetch would return ``None`` the moment the
        # server reports "no messages", which violates the "block
        # until shutdown" semantics when the caller passed
        # ``timeout=None``. Loop the fetch in that case so an empty
        # poll becomes a retry rather than a premature ``None``; the
        # shutdown event still wins via ``_fetch_with_shutdown``.
        if timeout is None:
            return await self._receive_blocking(channel_name, subscriber_id, sub)
        return await self._receive_with_timeout(
            channel_name, subscriber_id, sub, timeout
        )

    async def _receive_blocking(
        self,
        channel_name: str,
        subscriber_id: str,
        sub: Any,
    ) -> DeliveryEnvelope | None:
        """Block on a fetch loop until a message arrives or the bus stops."""
        while True:
            if self._shutdown_event.is_set():
                return None
            msgs = await self._fetch_with_shutdown(
                sub,
                _RECEIVE_POLL_WINDOW_SECONDS,
                channel_name=channel_name,
                subscriber_id=subscriber_id,
            )
            if msgs is None:
                return None
            if not msgs:
                continue
            envelope = await self._build_envelope(
                msgs,
                channel_name=channel_name,
                subscriber_id=subscriber_id,
            )
            # _build_envelope returns None when the fetched message was
            # oversized, malformed, or couldn't be acked. Those
            # conditions are per-message -- the next message in the
            # stream may be perfectly valid, so keep waiting instead of
            # returning None and ending the caller's receive loop.
            if envelope is not None:
                return envelope

    async def _receive_with_timeout(
        self,
        channel_name: str,
        subscriber_id: str,
        sub: Any,
        timeout: float,  # noqa: ASYNC109
    ) -> DeliveryEnvelope | None:
        """Wait up to ``timeout`` seconds across one or more fetch polls.

        Uses an absolute ``time.monotonic()`` deadline so the budget
        reflects real elapsed time. Subtracting the poll window from
        a running counter would double-count when a fetch returns
        before the window expires or when ``_build_envelope`` drops a
        message (the dropped-message path doesn't consume wall time
        proportional to the poll window).
        """
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0.0:
                return None
            if self._shutdown_event.is_set():
                return None
            poll = min(remaining, _RECEIVE_POLL_WINDOW_SECONDS)
            msgs = await self._fetch_with_shutdown(
                sub,
                poll,
                channel_name=channel_name,
                subscriber_id=subscriber_id,
            )
            if msgs is None:
                return None
            if not msgs:
                continue
            envelope = await self._build_envelope(
                msgs,
                channel_name=channel_name,
                subscriber_id=subscriber_id,
            )
            if envelope is not None:
                return envelope

    async def _resolve_consumer(
        self,
        channel_name: str,
        subscriber_id: str,
    ) -> Any:
        """Validate preconditions and return the durable pull consumer.

        Creates the consumer lazily for BROADCAST subscribers that
        have not called ``subscribe()`` explicitly. Resolves the
        channel through ``_resolve_channel_or_raise`` so a receiver
        in a different process than the publisher can still pull
        messages without first calling ``get_channel()``.
        """
        async with self._lock:
            self._require_running()
        await self._resolve_channel_or_raise(channel_name)
        async with self._lock:
            self._require_running()
            channel = self._channels[channel_name]
            if (
                channel.type != ChannelType.BROADCAST
                and subscriber_id not in channel.subscribers
            ):
                _raise_not_subscribed(channel_name, subscriber_id)
            key = (channel_name, subscriber_id)
            sub = self._subscriptions.get(key)
            if sub is None:
                await self._create_pull_consumer(
                    channel_name,
                    subscriber_id,
                    channel,
                )
                sub = self._subscriptions[key]
        return sub

    async def _fetch_with_shutdown(
        self,
        sub: Any,
        timeout: float,  # noqa: ASYNC109
        *,
        channel_name: str,
        subscriber_id: str,
    ) -> list[Any] | None:
        """Fetch at most one message, racing against the shutdown event.

        Returns ``None`` on shutdown, timeout, cancellation, or
        internal NATS errors; returns an empty list only if the fetch
        succeeded with no messages (shouldn't happen for batch=1 but
        handled defensively).
        """
        from nats.errors import TimeoutError as NatsTimeoutError  # noqa: PLC0415

        fetch_task: asyncio.Task[Any] = asyncio.create_task(
            sub.fetch(batch=1, timeout=timeout),
        )
        shutdown_task: asyncio.Task[Any] = asyncio.create_task(
            self._shutdown_event.wait(),
        )
        self._in_flight_fetches.add(fetch_task)
        self._in_flight_fetches.add(shutdown_task)

        try:
            done, _ = await asyncio.wait(
                {fetch_task, shutdown_task},
                return_when=asyncio.FIRST_COMPLETED,
            )
        except BaseException:
            fetch_task.cancel()
            shutdown_task.cancel()
            raise
        finally:
            self._in_flight_fetches.discard(fetch_task)
            self._in_flight_fetches.discard(shutdown_task)

        await _cancel_if_pending(fetch_task)
        await _cancel_if_pending(shutdown_task)

        if shutdown_task in done and fetch_task not in done:
            logger.debug(
                COMM_RECEIVE_SHUTDOWN,
                channel=channel_name,
                subscriber=subscriber_id,
            )
            return None

        try:
            result: list[Any] = fetch_task.result()
        except NatsTimeoutError:
            return []
        except asyncio.CancelledError:
            return None
        except Exception:
            logger.exception(
                COMM_BUS_RECEIVE_ERROR,
                channel=channel_name,
                subscriber=subscriber_id,
            )
            return None
        return result

    async def _try_ack(
        self,
        msg: Any,
        *,
        channel_name: str,
        subscriber_id: str,
    ) -> bool:
        """Attempt to ack a fetched JetStream message.

        Returns ``True`` on success, ``False`` on failure. Failures
        are logged with context so the caller can return ``None``
        instead of handing the message to the application and letting
        JetStream redeliver it under the same durable consumer.
        """
        try:
            await msg.ack()
        except Exception:
            logger.exception(
                COMM_BUS_RECEIVE_ERROR,
                channel=channel_name,
                subscriber=subscriber_id,
                phase="ack",
            )
            return False
        return True

    async def _build_envelope(
        self,
        msgs: list[Any] | None,
        *,
        channel_name: str,
        subscriber_id: str,
    ) -> DeliveryEnvelope | None:
        """Ack the fetched message and wrap it in a DeliveryEnvelope."""
        if not msgs:
            return None

        msg = msgs[0]
        if len(msg.data) > _MAX_BUS_PAYLOAD_BYTES:
            logger.warning(
                COMM_BUS_MESSAGE_TOO_LARGE,
                channel=channel_name,
                subscriber=subscriber_id,
                size=len(msg.data),
                limit=_MAX_BUS_PAYLOAD_BYTES,
            )
            # Ack the oversized payload so JetStream does not
            # redeliver it. Even if the ack fails we have already
            # decided not to surface the message, so swallowing the
            # error here is safe -- the worker sees the same outcome
            # either way.
            await self._try_ack(
                msg,
                channel_name=channel_name,
                subscriber_id=subscriber_id,
            )
            return None

        try:
            parsed = self._deserialize_message(msg.data)
        except ValueError as exc:
            logger.warning(
                COMM_BUS_MESSAGE_DESERIALIZE_FAILED,
                channel=channel_name,
                subscriber=subscriber_id,
                size=len(msg.data),
                error=str(exc),
            )
            # Same reasoning as the oversized branch: the message is
            # unusable regardless of whether ack succeeds.
            await self._try_ack(
                msg,
                channel_name=channel_name,
                subscriber_id=subscriber_id,
            )
            return None

        if not await self._try_ack(
            msg,
            channel_name=channel_name,
            subscriber_id=subscriber_id,
        ):
            # Returning the envelope after a failed ack would let
            # JetStream redeliver this exact message and cause the
            # caller to process it twice. Drop it instead.
            return None

        envelope = DeliveryEnvelope(
            message=parsed,
            channel_name=channel_name,
            delivered_at=datetime.now(UTC),
        )
        logger.debug(
            COMM_MESSAGE_DELIVERED,
            channel=channel_name,
            subscriber=subscriber_id,
            message_id=str(parsed.id),
            backend="nats",
        )
        return envelope

    async def create_channel(self, channel: Channel) -> Channel:
        """Create a new channel.

        Args:
            channel: Channel definition to create.

        Returns:
            The created channel.

        Raises:
            MessageBusNotRunningError: If not running.
            ChannelAlreadyExistsError: If the channel already exists.
        """
        async with self._lock:
            self._require_running()
            if channel.name in self._channels:
                logger.warning(
                    COMM_CHANNEL_ALREADY_EXISTS,
                    channel=channel.name,
                )
                msg = f"Channel already exists: {channel.name}"
                raise ChannelAlreadyExistsError(
                    msg,
                    context={"channel": channel.name},
                )
        # Check the distributed KV store so a peer process that
        # already created this channel is detected before we overwrite
        # its definition with our local copy.
        kv_existing = await self._load_channel_from_kv(channel.name)
        if kv_existing is not None:
            async with self._lock:
                if channel.name not in self._channels:
                    self._channels[channel.name] = kv_existing
            logger.warning(
                COMM_CHANNEL_ALREADY_EXISTS,
                channel=channel.name,
                source="kv",
            )
            msg = f"Channel already exists (peer-created): {channel.name}"
            raise ChannelAlreadyExistsError(
                msg,
                context={"channel": channel.name},
            )
        async with self._lock:
            # Re-check local cache after the KV round-trip in case a
            # concurrent local call created the channel while we were
            # checking KV.
            if channel.name in self._channels:
                logger.warning(
                    COMM_CHANNEL_ALREADY_EXISTS,
                    channel=channel.name,
                )
                msg = f"Channel already exists: {channel.name}"
                raise ChannelAlreadyExistsError(
                    msg,
                    context={"channel": channel.name},
                )
            self._channels[channel.name] = channel
            await self._write_channel_to_kv(channel)
        logger.info(
            COMM_CHANNEL_CREATED,
            channel=channel.name,
            type=str(channel.type),
            backend="nats",
        )
        return channel

    async def get_channel(self, channel_name: str) -> Channel:
        """Get a channel by name.

        Args:
            channel_name: Name of the channel.

        Returns:
            The channel.

        Raises:
            ChannelNotFoundError: If the channel does not exist.
        """
        return await self._resolve_channel_or_raise(channel_name)

    async def _resolve_channel_or_raise(self, channel_name: str) -> Channel:
        """Return a Channel from the local cache or the JetStream KV.

        Shared by ``get_channel``, ``subscribe``, ``receive`` and
        ``get_channel_history`` so a second process can observe
        channels created by another process on the same stream
        without having to call ``get_channel()`` first. The KV lookup
        happens outside the lock to avoid blocking other bus
        operations during the round-trip; the result is inserted
        under the lock to keep the cache consistent.
        """
        async with self._lock:
            cached = self._channels.get(channel_name)
        if cached is not None:
            return cached

        loaded = await self._load_channel_from_kv(channel_name)
        if loaded is None:
            _raise_channel_not_found(channel_name)

        async with self._lock:
            existing = self._channels.get(channel_name)
            if existing is not None:
                return existing
            self._channels[channel_name] = loaded
            return loaded

    async def list_channels(self) -> tuple[Channel, ...]:
        """List all channels, including those created by peer processes.

        Merges KV-stored channels with the local cache so callers get
        a complete view of the bus regardless of which process created
        each channel. KV read errors are logged and treated as
        non-fatal so the caller still gets the local cache.

        Returns:
            All registered channels (local + KV-discovered).
        """
        kv_channels = await self._scan_kv_channels()
        async with self._lock:
            for ch in kv_channels:
                if ch.name not in self._channels:
                    self._channels[ch.name] = ch
            return tuple(self._channels.values())

    async def _scan_kv_channels(self) -> list[Channel]:
        """Scan the KV bucket for all persisted channels."""
        if self._kv is None:
            return []
        try:
            keys = await self._kv.keys()
        except Exception as exc:
            logger.warning(
                COMM_BUS_KV_READ_FAILED,
                channel="*",
                error=str(exc),
                phase="list_channels_scan",
            )
            return []
        channels: list[Channel] = []
        for key in keys:
            try:
                decoded_name = _decode_token(key)
            except Exception as exc:
                logger.warning(
                    COMM_BUS_KV_READ_FAILED,
                    channel=key,
                    error=str(exc),
                    phase="decode_token",
                )
                continue
            entry = await self._fetch_kv_entry(decoded_name)
            if entry is None:
                continue
            ch = self._decode_kv_channel(decoded_name, entry)
            if ch is not None:
                channels.append(ch)
        return channels

    async def get_channel_history(
        self,
        channel_name: str,
        *,
        limit: int | None = None,
    ) -> tuple[Message, ...]:
        """Get message history for a channel.

        Queries JetStream for the most recent messages on the
        channel's subject. Uses ``_resolve_channel_or_raise`` so
        callers in a different process than the publisher can still
        inspect history without having to call ``get_channel()`` first.

        Args:
            channel_name: Channel to query.
            limit: Maximum number of most recent messages to return.
                ``None`` returns all retained messages (up to
                ``max_messages_per_channel``). ``<= 0`` returns
                an empty tuple.

        Returns:
            Messages in chronological order.

        Raises:
            ChannelNotFoundError: If the channel does not exist.
        """
        channel = await self._resolve_channel_or_raise(channel_name)
        async with self._lock:
            subject = self._subject_for_channel(channel)
            js = self._js

        if limit is not None and limit <= 0:
            logger.debug(
                COMM_HISTORY_QUERIED,
                channel=channel_name,
                count=0,
                limit=limit,
                backend="nats",
            )
            return ()

        max_to_return = (
            limit
            if limit is not None
            else self._config.retention.max_messages_per_channel
        )

        messages = await self._scan_stream_for_subject(
            js,
            subject=subject,
            max_to_return=max_to_return,
        )

        logger.debug(
            COMM_HISTORY_QUERIED,
            channel=channel_name,
            count=len(messages),
            limit=limit,
            backend="nats",
        )
        return tuple(messages)

    async def _scan_stream_for_subject(
        self,
        js: Any,
        *,
        subject: str,
        max_to_return: int,
    ) -> list[Message]:
        """Collect the most recent messages on a subject, oldest-first.

        Uses an ephemeral pull consumer with ``filter_subject`` so the
        NATS server does the subject filtering server-side and the
        client fetches in batches instead of walking the stream one
        sequence at a time. Retention is bounded by
        ``max_messages_per_channel``, so fetching every match for a
        single subject and slicing the tail is cheap and correct.

        Falls back to an empty list on any transport error so the
        history API degrades gracefully rather than propagating a
        backend exception to the caller.
        """
        if js is None:
            return []

        psub = await self._create_history_scan_consumer(js, subject)
        if psub is None:
            return []

        try:
            parsed_messages = await self._collect_history_batches(psub, subject)
        finally:
            await self._unsubscribe_history_consumer(psub, subject)

        if len(parsed_messages) <= max_to_return:
            return parsed_messages
        return parsed_messages[-max_to_return:]

    async def _create_history_scan_consumer(
        self,
        js: Any,
        subject: str,
    ) -> Any | None:
        """Create the ephemeral pull consumer used by history scans."""
        from nats.js.api import (  # noqa: PLC0415
            AckPolicy,
            ConsumerConfig,
            DeliverPolicy,
        )
        from nats.js.errors import NotFoundError  # noqa: PLC0415

        consumer_config = ConsumerConfig(
            deliver_policy=DeliverPolicy.ALL,
            ack_policy=AckPolicy.NONE,
            filter_subject=subject,
        )
        try:
            return await js.pull_subscribe(
                subject=subject,
                stream=self._stream_name,
                config=consumer_config,
            )
        except NotFoundError:
            return None
        except Exception as exc:
            logger.warning(
                COMM_BUS_STREAM_SCAN_FAILED,
                stream=self._stream_name,
                subject=subject,
                phase="subscribe",
                error=str(exc),
            )
            return None

    async def _collect_history_batches(
        self,
        psub: Any,
        subject: str,
    ) -> list[Message]:
        """Drain the history consumer into a list, stopping on idle timeout."""
        from nats.errors import TimeoutError as NatsTimeoutError  # noqa: PLC0415

        parsed_messages: list[Message] = []
        while True:
            try:
                batch = await psub.fetch(batch=100, timeout=0.5)
            except NatsTimeoutError:
                return parsed_messages
            except Exception as exc:
                logger.warning(
                    COMM_BUS_STREAM_SCAN_FAILED,
                    stream=self._stream_name,
                    subject=subject,
                    phase="fetch",
                    error=str(exc),
                )
                return parsed_messages
            if not batch:
                return parsed_messages
            for raw in batch:
                parsed = self._try_parse_matching(raw, subject)
                if parsed is not None:
                    parsed_messages.append(parsed)

    async def _unsubscribe_history_consumer(
        self,
        psub: Any,
        subject: str,
    ) -> None:
        """Best-effort teardown for an ephemeral history consumer."""
        try:
            await psub.unsubscribe()
        except Exception as exc:
            logger.warning(
                COMM_BUS_STREAM_SCAN_FAILED,
                stream=self._stream_name,
                subject=subject,
                phase="unsubscribe",
                error=str(exc),
            )

    def _try_parse_matching(
        self,
        raw: Any,
        subject: str,
    ) -> Message | None:
        """Parse the raw message if it matches the target subject."""
        if raw.subject != subject or raw.data is None:
            return None
        try:
            return self._deserialize_message(raw.data)
        except ValueError:
            logger.warning(
                COMM_BUS_MESSAGE_DESERIALIZE_FAILED,
                subject=subject,
                size=len(raw.data),
                phase="history_scan",
                exc_info=True,
            )
            return None
