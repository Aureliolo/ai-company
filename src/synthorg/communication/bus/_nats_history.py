"""History scanning: query JetStream for bounded message history.

Uses ephemeral pull consumers with ``DeliverPolicy.ALL`` and
``AckPolicy.NONE`` to scan a subject's history without affecting
durable consumer state.
"""

from typing import Any

from synthorg.communication.bus._nats_channels import (
    resolve_channel_or_raise,
    subject_for_channel,
)
from synthorg.communication.bus._nats_publish import deserialize_message
from synthorg.communication.bus._nats_state import _NatsState  # noqa: TC001
from synthorg.communication.message import Message  # noqa: TC001
from synthorg.observability import get_logger
from synthorg.observability.events.communication import (
    COMM_BUS_MESSAGE_DESERIALIZE_FAILED,
    COMM_BUS_STREAM_SCAN_FAILED,
    COMM_HISTORY_QUERIED,
)

logger = get_logger(__name__)


async def create_history_scan_consumer(
    js: Any,
    subject: str,
    stream_name: str,
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
            stream=stream_name,
            config=consumer_config,
        )
    except NotFoundError:
        return None
    except Exception as exc:
        logger.warning(
            COMM_BUS_STREAM_SCAN_FAILED,
            stream=stream_name,
            subject=subject,
            phase="subscribe",
            error=str(exc),
        )
        return None


async def collect_history_batches(
    psub: Any,
    subject: str,
    stream_name: str,
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
                stream=stream_name,
                subject=subject,
                phase="fetch",
                error=str(exc),
            )
            return parsed_messages
        if not batch:
            return parsed_messages
        for raw in batch:
            parsed = try_parse_matching(raw, subject)
            if parsed is not None:
                parsed_messages.append(parsed)


async def unsubscribe_history_consumer(
    psub: Any,
    subject: str,
    stream_name: str,
) -> None:
    """Best-effort teardown for an ephemeral history consumer."""
    try:
        await psub.unsubscribe()
    except Exception as exc:
        logger.warning(
            COMM_BUS_STREAM_SCAN_FAILED,
            stream=stream_name,
            subject=subject,
            phase="unsubscribe",
            error=str(exc),
        )


def try_parse_matching(raw: Any, subject: str) -> Message | None:
    """Parse the raw message if it matches the target subject."""
    if raw.subject != subject or raw.data is None:
        return None
    try:
        return deserialize_message(raw.data)
    except ValueError:
        logger.warning(
            COMM_BUS_MESSAGE_DESERIALIZE_FAILED,
            subject=subject,
            size=len(raw.data),
            phase="history_scan",
            exc_info=True,
        )
        return None


async def scan_stream_for_subject(
    state: _NatsState,
    js: Any,
    *,
    subject: str,
    max_to_return: int,
) -> list[Message]:
    """Collect the most recent messages on a subject, oldest-first."""
    if js is None:
        return []

    psub = await create_history_scan_consumer(js, subject, state.stream_name)
    if psub is None:
        return []

    try:
        parsed_messages = await collect_history_batches(
            psub, subject, state.stream_name
        )
    finally:
        await unsubscribe_history_consumer(psub, subject, state.stream_name)

    if len(parsed_messages) <= max_to_return:
        return parsed_messages
    return parsed_messages[-max_to_return:]


async def get_channel_history(
    state: _NatsState,
    channel_name: str,
    *,
    limit: int | None = None,
) -> tuple[Message, ...]:
    """Get message history for a channel."""
    channel = await resolve_channel_or_raise(state, channel_name)
    async with state.lock:
        prefix = state.nats_config.stream_name_prefix
        subject = subject_for_channel(prefix, channel)
        js = state.js

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
        limit if limit is not None else state.config.retention.max_messages_per_channel
    )

    messages = await scan_stream_for_subject(
        state,
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
