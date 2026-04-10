"""Unit tests for bus/persistence.py history accessor helpers.

Covers :func:`_apply_limit` and :class:`DequeHistoryAccessor` without
requiring a live NATS connection, so the replay/history query path
stays testable when the NATS backend is off.
"""

from collections import deque
from datetime import UTC, datetime

import pytest

from synthorg.communication.bus.persistence import (
    DequeHistoryAccessor,
    HistoryAccessor,
    _apply_limit,
)
from synthorg.communication.enums import MessageType
from synthorg.communication.message import Message, TextPart


def _make_message(content: str) -> Message:
    """Build a Message with a short text part for fixture use."""
    return Message(
        timestamp=datetime.now(UTC),
        sender="agent-a",
        to="agent-b",
        type=MessageType.TASK_UPDATE,
        channel="#test",
        parts=(TextPart(text=content),),
    )


class TestApplyLimit:
    """Limit-handling rules for MessageBus.get_channel_history()."""

    @pytest.mark.unit
    def test_none_limit_returns_all(self) -> None:
        messages = [_make_message(f"m{i}") for i in range(3)]
        assert _apply_limit(messages, None) == tuple(messages)

    @pytest.mark.unit
    def test_zero_limit_returns_empty(self) -> None:
        messages = [_make_message(f"m{i}") for i in range(3)]
        assert _apply_limit(messages, 0) == ()

    @pytest.mark.unit
    def test_negative_limit_returns_empty(self) -> None:
        messages = [_make_message(f"m{i}") for i in range(3)]
        assert _apply_limit(messages, -5) == ()

    @pytest.mark.unit
    def test_limit_exceeds_length_returns_all(self) -> None:
        messages = [_make_message(f"m{i}") for i in range(3)]
        assert _apply_limit(messages, 100) == tuple(messages)

    @pytest.mark.unit
    def test_limit_equals_length_returns_all(self) -> None:
        messages = [_make_message(f"m{i}") for i in range(3)]
        assert _apply_limit(messages, 3) == tuple(messages)

    @pytest.mark.unit
    def test_limit_less_than_length_returns_last_n(self) -> None:
        messages = [_make_message(f"m{i}") for i in range(5)]
        result = _apply_limit(messages, 2)
        assert len(result) == 2
        assert result[0].parts[0].text == "m3"  # type: ignore[union-attr]
        assert result[1].parts[0].text == "m4"  # type: ignore[union-attr]

    @pytest.mark.unit
    def test_empty_input(self) -> None:
        assert _apply_limit([], None) == ()
        assert _apply_limit([], 5) == ()


class TestDequeHistoryAccessor:
    """DequeHistoryAccessor wraps the in-memory bus deque map."""

    @pytest.mark.unit
    def test_implements_protocol(self) -> None:
        accessor = DequeHistoryAccessor(histories={})
        assert isinstance(accessor, HistoryAccessor)

    @pytest.mark.unit
    async def test_missing_channel_returns_empty(self) -> None:
        accessor = DequeHistoryAccessor(histories={})
        assert await accessor.get_history("#nonexistent") == ()

    @pytest.mark.unit
    async def test_returns_chronological_slice(self) -> None:
        bucket: deque[Message] = deque(
            [_make_message(f"m{i}") for i in range(3)],
            maxlen=10,
        )
        accessor = DequeHistoryAccessor(histories={"#general": bucket})
        result = await accessor.get_history("#general")
        assert len(result) == 3
        assert result[0].parts[0].text == "m0"  # type: ignore[union-attr]
        assert result[-1].parts[0].text == "m2"  # type: ignore[union-attr]

    @pytest.mark.unit
    async def test_limit_applied(self) -> None:
        bucket: deque[Message] = deque(
            [_make_message(f"m{i}") for i in range(5)],
            maxlen=10,
        )
        accessor = DequeHistoryAccessor(histories={"#general": bucket})
        result = await accessor.get_history("#general", limit=2)
        assert len(result) == 2
        assert result[0].parts[0].text == "m3"  # type: ignore[union-attr]
        assert result[1].parts[0].text == "m4"  # type: ignore[union-attr]

    @pytest.mark.unit
    async def test_limit_zero_short_circuits(self) -> None:
        bucket: deque[Message] = deque(
            [_make_message(f"m{i}") for i in range(3)],
            maxlen=10,
        )
        accessor = DequeHistoryAccessor(histories={"#general": bucket})
        assert await accessor.get_history("#general", limit=0) == ()

    @pytest.mark.unit
    async def test_deque_maxlen_respected(self) -> None:
        """The accessor reflects the bus's bounded-history behavior."""
        bucket: deque[Message] = deque(maxlen=3)
        for i in range(5):
            bucket.append(_make_message(f"m{i}"))
        accessor = DequeHistoryAccessor(histories={"#general": bucket})
        result = await accessor.get_history("#general")
        # Only the last 3 should remain; m0 and m1 were pushed out.
        assert len(result) == 3
        assert result[0].parts[0].text == "m2"  # type: ignore[union-attr]
        assert result[-1].parts[0].text == "m4"  # type: ignore[union-attr]
