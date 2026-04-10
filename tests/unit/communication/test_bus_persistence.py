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

    @staticmethod
    def _labels(result: tuple[Message, ...]) -> list[str]:
        """Return the text payloads of each message for easy comparison."""
        out: list[str] = []
        for msg in result:
            first = msg.parts[0]
            text = getattr(first, "text", None)
            if text is None:
                pytest.fail(f"unexpected part type: {type(first)!r}")
            out.append(text)
        return out

    @pytest.mark.unit
    @pytest.mark.parametrize(
        ("input_count", "limit", "expected_labels"),
        [
            # limit=None returns everything
            (3, None, ["m0", "m1", "m2"]),
            # limit=0 / negative -> empty tuple
            (3, 0, []),
            (3, -5, []),
            # limit >= length -> everything
            (3, 100, ["m0", "m1", "m2"]),
            (3, 3, ["m0", "m1", "m2"]),
            # limit < length -> last N in chronological order
            (5, 2, ["m3", "m4"]),
            (5, 4, ["m1", "m2", "m3", "m4"]),
            # empty input for both None and positive limit
            (0, None, []),
            (0, 5, []),
        ],
    )
    def test_apply_limit_various(
        self,
        input_count: int,
        limit: int | None,
        expected_labels: list[str],
    ) -> None:
        messages = [_make_message(f"m{i}") for i in range(input_count)]
        result = _apply_limit(messages, limit)
        assert self._labels(result) == expected_labels


class TestDequeHistoryAccessor:
    """DequeHistoryAccessor wraps the in-memory bus deque map."""

    @pytest.mark.unit
    def test_implements_protocol(self) -> None:
        accessor = DequeHistoryAccessor(histories={})
        assert isinstance(accessor, HistoryAccessor)

    @pytest.mark.unit
    async def test_missing_channel_raises(self) -> None:
        """Missing channels must raise ChannelNotFoundError.

        Returning an empty tuple would conflate "channel does not
        exist" with "channel exists but has no messages", breaking the
        ``MessageBus.get_channel_history`` protocol contract for any
        backend that delegates directly to this accessor.
        """
        from synthorg.communication.errors import ChannelNotFoundError

        accessor = DequeHistoryAccessor(histories={})
        with pytest.raises(ChannelNotFoundError):
            await accessor.get_history("#nonexistent")

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
