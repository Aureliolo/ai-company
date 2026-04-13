"""Tests for EventStreamHub."""

import asyncio
from datetime import UTC, datetime

import pytest

from synthorg.communication.event_stream.stream import EventStreamHub
from synthorg.communication.event_stream.types import AgUiEventType, StreamEvent

_TS = datetime(2026, 4, 13, tzinfo=UTC)


def _make_event(
    session_id: str = "session-abc",
    event_type: AgUiEventType = AgUiEventType.RUN_STARTED,
) -> StreamEvent:
    return StreamEvent(
        id="evt-001",
        type=event_type,
        timestamp=_TS,
        session_id=session_id,
    )


@pytest.mark.unit
class TestEventStreamHub:
    async def test_subscribe_returns_queue(self) -> None:
        hub = EventStreamHub()
        queue = hub.subscribe("session-abc")
        assert isinstance(queue, asyncio.Queue)

    async def test_publish_delivers_to_subscriber(self) -> None:
        hub = EventStreamHub()
        queue = hub.subscribe("session-abc")
        event = _make_event()
        await hub.publish(event)
        received = queue.get_nowait()
        assert received.id == "evt-001"

    async def test_publish_fans_out_to_multiple_subscribers(self) -> None:
        hub = EventStreamHub()
        q1 = hub.subscribe("session-abc")
        q2 = hub.subscribe("session-abc")
        event = _make_event()
        await hub.publish(event)
        assert q1.get_nowait().id == "evt-001"
        assert q2.get_nowait().id == "evt-001"

    async def test_publish_only_to_matching_session(self) -> None:
        hub = EventStreamHub()
        q_abc = hub.subscribe("session-abc")
        q_xyz = hub.subscribe("session-xyz")
        event = _make_event(session_id="session-abc")
        await hub.publish(event)
        assert q_xyz.empty() is not False or q_xyz.qsize() == 0
        assert q_abc.get_nowait().id == "evt-001"
        assert q_xyz.empty()

    async def test_unsubscribe_removes_queue(self) -> None:
        hub = EventStreamHub()
        queue = hub.subscribe("session-abc")
        hub.unsubscribe("session-abc", queue)
        event = _make_event()
        await hub.publish(event)
        assert queue.empty()

    async def test_unsubscribe_unknown_session_no_error(self) -> None:
        hub = EventStreamHub()
        queue: asyncio.Queue[StreamEvent] = asyncio.Queue()
        hub.unsubscribe("nonexistent", queue)

    async def test_publish_to_session_with_no_subscribers(self) -> None:
        hub = EventStreamHub()
        event = _make_event(session_id="orphan")
        await hub.publish(event)  # should not raise

    async def test_full_queue_does_not_block(self) -> None:
        hub = EventStreamHub(max_queue_size=1)
        queue = hub.subscribe("session-abc")
        e1 = _make_event()
        e2 = StreamEvent(
            id="evt-002",
            type=AgUiEventType.RUN_FINISHED,
            timestamp=_TS,
            session_id="session-abc",
        )
        await hub.publish(e1)
        await hub.publish(e2)  # queue full, should not block
        assert queue.qsize() == 1  # first event kept, second dropped

    async def test_publish_raw_convenience(self) -> None:
        hub = EventStreamHub()
        queue = hub.subscribe("session-abc")
        await hub.publish_raw(
            session_id="session-abc",
            event_type=AgUiEventType.STEP_STARTED,
            agent_id="agent-001",
            payload={"step": 1},
        )
        event = queue.get_nowait()
        assert event.type == AgUiEventType.STEP_STARTED
        assert event.agent_id == "agent-001"
        assert event.payload["step"] == 1

    async def test_multiple_sessions_isolated(self) -> None:
        hub = EventStreamHub()
        q1 = hub.subscribe("s1")
        q2 = hub.subscribe("s2")
        await hub.publish(_make_event(session_id="s1"))
        await hub.publish(
            StreamEvent(
                id="evt-s2",
                type=AgUiEventType.RUN_FINISHED,
                timestamp=_TS,
                session_id="s2",
            ),
        )
        assert q1.get_nowait().session_id == "s1"
        assert q2.get_nowait().session_id == "s2"
        assert q1.empty()
        assert q2.empty()
