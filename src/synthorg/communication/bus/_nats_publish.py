"""Publishing: publish to channels and send direct messages.

Includes message serialization/deserialization and the JetStream
publish-with-ack wrapper.
"""

import asyncio

from synthorg.communication.bus._nats_channels import (
    direct_subject as _direct_subject,
)
from synthorg.communication.bus._nats_channels import (
    ensure_direct_channel,
    resolve_channel_or_raise,
    subject_for_channel,
)
from synthorg.communication.bus._nats_state import _NatsState  # noqa: TC001
from synthorg.communication.bus._nats_utils import (
    DM_SEPARATOR,
    MAX_BUS_PAYLOAD_BYTES,
    require_running,
)
from synthorg.communication.errors import MessageBusNotRunningError
from synthorg.communication.message import Message
from synthorg.observability import get_logger
from synthorg.observability.events.communication import (
    COMM_DIRECT_SENT,
    COMM_MESSAGE_PUBLISHED,
    COMM_SEND_DIRECT_INVALID,
)

logger = get_logger(__name__)


def serialize_message(message: Message) -> bytes:
    """Serialize a Message to JSON bytes for the wire."""
    return message.model_dump_json(by_alias=True).encode("utf-8")


def deserialize_message(data: bytes) -> Message:
    """Reconstruct a Message from wire JSON bytes."""
    return Message.model_validate_json(data.decode("utf-8"))


async def publish_with_ack(
    state: _NatsState,
    subject: str,
    payload: bytes,
) -> None:
    """Publish to JetStream waiting for server ack."""
    if state.js is None:
        msg = "JetStream context not initialized"
        raise MessageBusNotRunningError(msg)
    await asyncio.wait_for(
        state.js.publish(subject, payload),
        timeout=state.nats_config.publish_ack_wait_seconds,
    )


async def publish(state: _NatsState, message: Message) -> None:
    """Publish a message to its channel via the JetStream stream."""
    async with state.lock:
        require_running(state)
    channel_name = message.channel
    channel = await resolve_channel_or_raise(state, channel_name)
    prefix = state.nats_config.stream_name_prefix
    subject = subject_for_channel(prefix, channel)

    payload = serialize_message(message)
    if len(payload) > MAX_BUS_PAYLOAD_BYTES:
        msg = (
            f"Serialized message exceeds bus payload limit: "
            f"{len(payload)} > {MAX_BUS_PAYLOAD_BYTES}"
        )
        logger.warning(COMM_SEND_DIRECT_INVALID, error=msg, channel=channel_name)
        raise ValueError(msg)
    await publish_with_ack(state, subject, payload)

    logger.info(
        COMM_MESSAGE_PUBLISHED,
        channel=channel_name,
        message_id=str(message.id),
        type=str(message.type),
        backend="nats",
    )


async def send_direct(
    state: _NatsState,
    message: Message,
    *,
    recipient: str,
) -> None:
    """Send a direct message, creating the DIRECT channel lazily."""
    sender = message.sender
    if message.to != recipient:
        msg = f"recipient={recipient!r} does not match message.to={message.to!r}"
        logger.warning(COMM_SEND_DIRECT_INVALID, error=msg)
        raise ValueError(msg)
    for agent_id in (sender, recipient):
        if DM_SEPARATOR in agent_id:
            msg = (
                f"Agent ID {agent_id!r} contains the reserved "
                f"separator character {DM_SEPARATOR!r}"
            )
            logger.warning(COMM_SEND_DIRECT_INVALID, error=msg)
            raise ValueError(msg)
    a, b = sorted([sender, recipient])
    pair = (a, b)
    channel_name = f"@{pair[0]}:{pair[1]}"

    async with state.lock:
        require_running(state)
        await ensure_direct_channel(state, channel_name, pair)
        state.known_agents.add(sender)
        state.known_agents.add(recipient)

    prefix = state.nats_config.stream_name_prefix
    subject = _direct_subject(prefix, channel_name)
    payload = serialize_message(message)
    if len(payload) > MAX_BUS_PAYLOAD_BYTES:
        msg = (
            f"Serialized direct message exceeds bus payload limit: "
            f"{len(payload)} > {MAX_BUS_PAYLOAD_BYTES}"
        )
        logger.warning(COMM_SEND_DIRECT_INVALID, error=msg, channel=channel_name)
        raise ValueError(msg)
    await publish_with_ack(state, subject, payload)

    logger.info(
        COMM_DIRECT_SENT,
        channel=channel_name,
        sender=sender,
        recipient=recipient,
        message_id=str(message.id),
        backend="nats",
    )
