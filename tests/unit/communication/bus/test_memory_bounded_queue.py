"""Subscriber-queue bounding tests for the in-memory bus.

The un-bounded ``asyncio.Queue()`` at ``bus/memory.py:201`` lets a
publisher outrun a slow subscriber indefinitely. These tests pin the
drop-newest policy and the ``COMM_SUBSCRIBER_QUEUE_OVERFLOW`` signal
so a regression to unbounded behavior is immediately visible.
"""

from datetime import UTC, datetime

import pytest
import structlog.testing

from synthorg.communication.bus.memory import InMemoryMessageBus
from synthorg.communication.config import (
    MessageBusConfig,
    MessageRetentionConfig,
)
from synthorg.communication.enums import MessagePriority, MessageType
from synthorg.communication.message import Message
from synthorg.observability.events.communication import (
    COMM_SUBSCRIBER_QUEUE_OVERFLOW,
)


def _message(channel: str, sender: str, to: str, idx: int) -> Message:
    """Build a minimal text message for a test publish."""
    return Message.model_validate(
        {
            "from": sender,
            "to": to,
            "channel": channel,
            "parts": [{"type": "text", "text": f"msg-{idx}"}],
            "type": MessageType.TASK_UPDATE,
            "priority": MessagePriority.NORMAL,
            "timestamp": datetime.now(UTC),
        }
    )


@pytest.mark.unit
class TestBoundedSubscriberQueue:
    """The subscriber queue must be bounded by ``max_subscriber_queue_size``."""

    async def test_publish_drops_newest_on_overflow(self) -> None:
        """Once a subscriber queue is full, further publishes drop newest.

        Invariants:

        - the first ``max_subscriber_queue_size`` envelopes remain queued
        - subsequent publishes do NOT raise ``QueueFull``
        - each overflow emits ``COMM_SUBSCRIBER_QUEUE_OVERFLOW`` at
          WARNING with ``drop_policy="newest"`` and ``backend="memory"``
        """
        max_queue_size = 4
        overflow_count = 2
        channel = "#engineering"
        config = MessageBusConfig(
            channels=(channel,),
            retention=MessageRetentionConfig(
                max_messages_per_channel=1000,
                max_subscriber_queue_size=max_queue_size,
            ),
        )
        bus = InMemoryMessageBus(config=config)
        await bus.start()
        try:
            subscriber = "agent-slow-001"
            await bus.subscribe(channel, subscriber)

            with structlog.testing.capture_logs() as captured:
                total = max_queue_size + overflow_count
                for idx in range(total):
                    # Publisher never blocks or raises on an overflowed
                    # subscriber -- slow consumer must not nuke the channel.
                    await bus.publish(
                        _message(channel, sender="alice", to=subscriber, idx=idx),
                    )

            queue = bus._queues[(channel, subscriber)]
            actual_qsize = queue.qsize()
            assert actual_qsize == max_queue_size, (
                f"expected queue to hold {max_queue_size} envelopes, got {actual_qsize}"
            )

            overflow_events = [
                e for e in captured if e.get("event") == COMM_SUBSCRIBER_QUEUE_OVERFLOW
            ]
            assert len(overflow_events) == overflow_count, (
                f"expected {overflow_count} overflow events, got {captured!r}"
            )
            for event in overflow_events:
                assert event["drop_policy"] == "newest", event
                assert event["backend"] == "memory", event
                assert event["channel"] == channel, event
                assert event["subscriber"] == subscriber, event
                assert event["log_level"] == "warning", event
        finally:
            # Stop in finally so a failed assertion above does not leak
            # a running InMemoryMessageBus into the next test (would
            # show up as a vitest-style async leak in the unit run).
            await bus.stop()

    async def test_publish_preserves_oldest_envelopes(self) -> None:
        """The drop-newest policy keeps older envelopes intact."""
        max_queue_size = 3
        channel = "#engineering"
        config = MessageBusConfig(
            channels=(channel,),
            retention=MessageRetentionConfig(
                max_messages_per_channel=1000,
                max_subscriber_queue_size=max_queue_size,
            ),
        )
        bus = InMemoryMessageBus(config=config)
        await bus.start()
        try:
            subscriber = "agent-slow-002"
            await bus.subscribe(channel, subscriber)

            for idx in range(max_queue_size + 3):
                await bus.publish(
                    _message(channel, sender="alice", to=subscriber, idx=idx),
                )

            # Drain the queue and verify the first ``max_queue_size``
            # envelopes are what we see -- dropped envelopes are the
            # NEWEST arrivals, not the oldest.
            received: list[int] = []
            for _ in range(max_queue_size):
                envelope = await bus.receive(channel, subscriber, timeout=0.1)
                assert envelope is not None
                text = envelope.message.parts[0].text  # type: ignore[union-attr]
                received.append(int(text.removeprefix("msg-")))

            assert received == list(range(max_queue_size)), (
                f"drop-newest preserves oldest entries; got {received}"
            )
        finally:
            await bus.stop()
