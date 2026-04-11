"""Webhook event bus bridge.

Publishes verified webhook events onto the SynthOrg message bus
so that ``ExternalTriggerStrategy`` and other consumers can react.
"""

from datetime import UTC, datetime
from typing import Any

from synthorg.communication.bus_protocol import MessageBus  # noqa: TC001
from synthorg.communication.channel import Channel
from synthorg.communication.enums import ChannelType
from synthorg.communication.message import DataPart, Message
from synthorg.observability import get_logger
from synthorg.observability.events.integrations import (
    WEBHOOK_EVENT_PUBLISH_FAILED,
    WEBHOOK_EVENT_PUBLISHED,
)

logger = get_logger(__name__)

WEBHOOK_CHANNEL = Channel(name="#webhooks", type=ChannelType.TOPIC)


async def publish_webhook_event(
    *,
    bus: MessageBus,
    connection_name: str,
    event_type: str,
    payload: dict[str, Any],
) -> None:
    """Publish a verified webhook event to the message bus.

    Args:
        bus: The message bus instance.
        connection_name: Source connection name.
        event_type: Provider-specific event type.
        payload: Webhook payload dict.
    """
    message = Message(
        sender="integrations:webhook-receiver",
        to=WEBHOOK_CHANNEL.name,
        type="webhook_event",
        channel=WEBHOOK_CHANNEL.name,
        parts=(
            DataPart(
                data={
                    "connection_name": connection_name,
                    "event_type": event_type,
                    "payload": payload,
                    "received_at": datetime.now(UTC).isoformat(),
                },
            ),
        ),
    )
    try:
        await bus.publish(message)
        logger.info(
            WEBHOOK_EVENT_PUBLISHED,
            connection_name=connection_name,
            event_type=event_type,
        )
    except Exception:
        logger.exception(
            WEBHOOK_EVENT_PUBLISH_FAILED,
            connection_name=connection_name,
            event_type=event_type,
        )
