"""Message reception: fetch loop, ack, envelope building.

The core complexity of the bus -- racing fetch against shutdown,
handling timeouts, building delivery envelopes, and acking messages.
"""

import asyncio
import time
from datetime import UTC, datetime
from typing import Any

from synthorg.communication.bus._nats_channels import resolve_channel_or_raise
from synthorg.communication.bus._nats_consumers import create_pull_consumer
from synthorg.communication.bus._nats_publish import deserialize_message
from synthorg.communication.bus._nats_state import _NatsState  # noqa: TC001
from synthorg.communication.bus._nats_utils import (
    MAX_BUS_PAYLOAD_BYTES,
    RECEIVE_POLL_WINDOW_SECONDS,
    cancel_if_pending,
    raise_not_subscribed,
    require_running,
)
from synthorg.communication.enums import ChannelType
from synthorg.communication.subscription import DeliveryEnvelope
from synthorg.observability import get_logger
from synthorg.observability.events.communication import (
    COMM_BUS_MESSAGE_DESERIALIZE_FAILED,
    COMM_BUS_MESSAGE_TOO_LARGE,
    COMM_BUS_RECEIVE_ERROR,
    COMM_MESSAGE_DELIVERED,
    COMM_RECEIVE_SHUTDOWN,
    COMM_SUBSCRIBER_QUEUE_OVERFLOW,
)

_OVERFLOW_LOG_INTERVAL_SECONDS: float = 60.0
"""Minimum seconds between per-subscriber overflow emissions.

JetStream pauses delivery to a consumer once its unacked count hits
``max_ack_pending``. Without this rate-limit an observer polling a
paused consumer would flood logs every poll; once per minute per
subscriber matches operator dashboard refresh cadence.
"""

logger = get_logger(__name__)


async def resolve_consumer(
    state: _NatsState,
    channel_name: str,
    subscriber_id: str,
) -> Any:
    """Validate preconditions and return the durable pull consumer.

    Creates the consumer lazily for BROADCAST subscribers.
    """
    async with state.lock:
        require_running(state)
    await resolve_channel_or_raise(state, channel_name)
    async with state.lock:
        require_running(state)
        channel = state.channels[channel_name]
        if (
            channel.type != ChannelType.BROADCAST
            and subscriber_id not in channel.subscribers
        ):
            raise_not_subscribed(channel_name, subscriber_id)
        key = (channel_name, subscriber_id)
        sub = state.subscriptions.get(key)
        if sub is None:
            await create_pull_consumer(
                state,
                channel_name,
                subscriber_id,
                channel,
            )
            sub = state.subscriptions[key]
    return sub


async def _maybe_log_overflow(
    state: _NatsState,
    sub: Any,
    *,
    channel_name: str,
    subscriber_id: str,
) -> None:
    """Emit ``COMM_SUBSCRIBER_QUEUE_OVERFLOW`` if the consumer is paused.

    Called from the receive path when a fetch returns empty. Queries
    ``consumer_info()`` to check whether ``num_ack_pending`` has hit
    the configured ``max_ack_pending`` cap -- the observable signal
    that JetStream has paused delivery to this consumer. Rate-limited
    per ``(channel, subscriber)`` at
    :data:`_OVERFLOW_LOG_INTERVAL_SECONDS`.

    Best-effort: ``consumer_info()`` failures are swallowed so an
    observability probe never breaks the receive loop.
    """
    cap = state.config.retention.max_subscriber_queue_size
    key = (channel_name, subscriber_id)
    now = time.monotonic()
    last = state.last_overflow_log.get(key, 0.0)
    if now - last < _OVERFLOW_LOG_INTERVAL_SECONDS:
        return
    # Claim the rate-limit slot *before* awaiting ``consumer_info()``
    # so concurrent callers on the same ``(channel, subscriber)`` key
    # cannot all pass the window check and pile on duplicate probes
    # + log entries. The timestamp is cleared only on a caller that
    # actually observes a healthy (non-paused) consumer, so the next
    # genuine overflow after a recovery window is still reported
    # within ``_OVERFLOW_LOG_INTERVAL_SECONDS``.
    state.last_overflow_log[key] = now
    try:
        info = await sub.consumer_info()
    except MemoryError, RecursionError:
        raise
    except Exception:
        return
    num_pending = getattr(info, "num_ack_pending", 0)
    if num_pending < cap:
        return
    logger.warning(
        COMM_SUBSCRIBER_QUEUE_OVERFLOW,
        channel=channel_name,
        subscriber=subscriber_id,
        queue_size=cap,
        drop_policy="delivery_paused",
        backend="nats",
        num_ack_pending=num_pending,
    )


async def fetch_with_shutdown(
    state: _NatsState,
    sub: Any,
    timeout: float,  # noqa: ASYNC109
    *,
    channel_name: str,
    subscriber_id: str,
) -> list[Any] | None:
    """Fetch at most one message, racing against the shutdown event.

    Returns ``None`` on shutdown, cancellation, or internal errors;
    an empty list on clean timeout.
    """
    from nats.errors import TimeoutError as NatsTimeoutError  # noqa: PLC0415

    fetch_task: asyncio.Task[Any] = asyncio.create_task(
        sub.fetch(batch=1, timeout=timeout),
    )
    shutdown_task: asyncio.Task[Any] = asyncio.create_task(
        state.shutdown_event.wait(),
    )
    state.in_flight_fetches.add(fetch_task)
    state.in_flight_fetches.add(shutdown_task)

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
        state.in_flight_fetches.discard(fetch_task)
        state.in_flight_fetches.discard(shutdown_task)

    await cancel_if_pending(fetch_task)
    await cancel_if_pending(shutdown_task)

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


async def try_ack(
    msg: Any,
    *,
    channel_name: str,
    subscriber_id: str,
) -> bool:
    """Attempt to ack a fetched JetStream message.

    Returns ``True`` on success, ``False`` on failure.
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


async def build_envelope(
    msgs: list[Any] | None,
    *,
    channel_name: str,
    subscriber_id: str,
) -> DeliveryEnvelope | None:
    """Ack the fetched message and wrap it in a DeliveryEnvelope."""
    if not msgs:
        return None

    msg = msgs[0]
    if len(msg.data) > MAX_BUS_PAYLOAD_BYTES:
        logger.warning(
            COMM_BUS_MESSAGE_TOO_LARGE,
            channel=channel_name,
            subscriber=subscriber_id,
            size=len(msg.data),
            limit=MAX_BUS_PAYLOAD_BYTES,
        )
        await try_ack(
            msg,
            channel_name=channel_name,
            subscriber_id=subscriber_id,
        )
        return None

    try:
        parsed = deserialize_message(msg.data)
    except ValueError as exc:
        logger.warning(
            COMM_BUS_MESSAGE_DESERIALIZE_FAILED,
            channel=channel_name,
            subscriber=subscriber_id,
            size=len(msg.data),
            error=str(exc),
        )
        await try_ack(
            msg,
            channel_name=channel_name,
            subscriber_id=subscriber_id,
        )
        return None

    if not await try_ack(
        msg,
        channel_name=channel_name,
        subscriber_id=subscriber_id,
    ):
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


async def receive_blocking(
    state: _NatsState,
    channel_name: str,
    subscriber_id: str,
    sub: Any,
) -> DeliveryEnvelope | None:
    """Block on a fetch loop until a message arrives or the bus stops."""
    while True:
        if state.shutdown_event.is_set():
            return None
        msgs = await fetch_with_shutdown(
            state,
            sub,
            RECEIVE_POLL_WINDOW_SECONDS,
            channel_name=channel_name,
            subscriber_id=subscriber_id,
        )
        if msgs is None:
            return None
        if not msgs:
            await _maybe_log_overflow(
                state,
                sub,
                channel_name=channel_name,
                subscriber_id=subscriber_id,
            )
            continue
        envelope = await build_envelope(
            msgs,
            channel_name=channel_name,
            subscriber_id=subscriber_id,
        )
        if envelope is not None:
            return envelope


async def receive_with_timeout(
    state: _NatsState,
    channel_name: str,
    subscriber_id: str,
    sub: Any,
    timeout: float,  # noqa: ASYNC109
) -> DeliveryEnvelope | None:
    """Wait up to ``timeout`` seconds across one or more fetch polls."""
    deadline = time.monotonic() + timeout
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0.0:
            return None
        if state.shutdown_event.is_set():
            return None
        poll = min(remaining, RECEIVE_POLL_WINDOW_SECONDS)
        msgs = await fetch_with_shutdown(
            state,
            sub,
            poll,
            channel_name=channel_name,
            subscriber_id=subscriber_id,
        )
        if msgs is None:
            return None
        if not msgs:
            await _maybe_log_overflow(
                state,
                sub,
                channel_name=channel_name,
                subscriber_id=subscriber_id,
            )
            continue
        envelope = await build_envelope(
            msgs,
            channel_name=channel_name,
            subscriber_id=subscriber_id,
        )
        if envelope is not None:
            return envelope


async def receive(
    state: _NatsState,
    channel_name: str,
    subscriber_id: str,
    *,
    timeout: float | None = None,  # noqa: ASYNC109
) -> DeliveryEnvelope | None:
    """Receive the next message from the durable consumer."""
    sub = await resolve_consumer(state, channel_name, subscriber_id)
    if timeout is None:
        return await receive_blocking(state, channel_name, subscriber_id, sub)
    return await receive_with_timeout(state, channel_name, subscriber_id, sub, timeout)
