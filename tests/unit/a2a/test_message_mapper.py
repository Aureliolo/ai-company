"""Tests for Message <-> A2AMessage bidirectional mapping."""

from datetime import UTC, datetime

import pytest

from synthorg.a2a.message_mapper import from_a2a, to_a2a
from synthorg.a2a.models import (
    A2ADataPart,
    A2AFilePart,
    A2AMessage,
    A2AMessageRole,
    A2ATextPart,
)
from synthorg.communication.enums import MessageType
from synthorg.communication.message import (
    DataPart,
    FilePart,
    Message,
    TextPart,
    UriPart,
)


def _make_message(
    *,
    msg_type: MessageType = MessageType.TASK_UPDATE,
    parts: tuple[TextPart | DataPart | FilePart | UriPart, ...] = (
        TextPart(text="hello"),
    ),
) -> Message:
    """Create a minimal internal Message for testing."""
    return Message(
        timestamp=datetime.now(UTC),
        sender="agent-a",
        to="agent-b",
        type=msg_type,
        channel="test-channel",
        parts=parts,
    )


class TestToA2A:
    """Internal Message -> A2AMessage."""

    @pytest.mark.unit
    def test_text_part(self) -> None:
        """TextPart maps to A2ATextPart."""
        msg = _make_message(parts=(TextPart(text="hello"),))
        a2a = to_a2a(msg)
        assert len(a2a.parts) == 1
        assert isinstance(a2a.parts[0], A2ATextPart)
        assert a2a.parts[0].text == "hello"

    @pytest.mark.unit
    def test_data_part(self) -> None:
        """DataPart maps to A2ADataPart."""
        part = DataPart(data={"key": "value"})  # type: ignore[arg-type]
        msg = _make_message(parts=(part,))
        a2a = to_a2a(msg)
        assert len(a2a.parts) == 1
        assert isinstance(a2a.parts[0], A2ADataPart)
        assert a2a.parts[0].data == {"key": "value"}

    @pytest.mark.unit
    def test_file_part(self) -> None:
        """FilePart maps to A2AFilePart."""
        part = FilePart(
            uri="https://example.com/f.pdf",
            mime_type="application/pdf",
        )
        msg = _make_message(parts=(part,))
        a2a = to_a2a(msg)
        assert len(a2a.parts) == 1
        assert isinstance(a2a.parts[0], A2AFilePart)
        assert a2a.parts[0].uri == "https://example.com/f.pdf"

    @pytest.mark.unit
    def test_uri_part_to_text(self) -> None:
        """UriPart (no A2A equivalent) maps to A2ATextPart."""
        msg = _make_message(parts=(UriPart(uri="https://example.com"),))
        a2a = to_a2a(msg)
        assert len(a2a.parts) == 1
        assert isinstance(a2a.parts[0], A2ATextPart)
        assert a2a.parts[0].text == "https://example.com"

    @pytest.mark.unit
    def test_multi_part(self) -> None:
        """Multiple parts are mapped preserving order."""
        msg = _make_message(
            parts=(
                TextPart(text="first"),
                DataPart(data={"n": 1}),  # type: ignore[arg-type]
                TextPart(text="last"),
            ),
        )
        a2a = to_a2a(msg)
        assert len(a2a.parts) == 3
        assert isinstance(a2a.parts[0], A2ATextPart)
        assert isinstance(a2a.parts[1], A2ADataPart)
        assert isinstance(a2a.parts[2], A2ATextPart)

    @pytest.mark.unit
    def test_delegation_maps_to_user_role(self) -> None:
        """DELEGATION message type maps to user role."""
        msg = _make_message(msg_type=MessageType.DELEGATION)
        a2a = to_a2a(msg)
        assert a2a.role == A2AMessageRole.USER

    @pytest.mark.unit
    def test_task_update_maps_to_agent_role(self) -> None:
        """TASK_UPDATE message type maps to agent role."""
        msg = _make_message(msg_type=MessageType.TASK_UPDATE)
        a2a = to_a2a(msg)
        assert a2a.role == A2AMessageRole.AGENT


class TestFromA2A:
    """A2AMessage -> Internal Message."""

    @pytest.mark.unit
    def test_text_part(self) -> None:
        """A2ATextPart maps to TextPart."""
        a2a = A2AMessage(
            role=A2AMessageRole.AGENT,
            parts=(A2ATextPart(text="response"),),
        )
        msg = from_a2a(
            a2a,
            channel="test",
            sender="external",
            recipient="internal",
        )
        assert len(msg.parts) == 1
        assert isinstance(msg.parts[0], TextPart)
        assert msg.parts[0].text == "response"

    @pytest.mark.unit
    def test_user_role_maps_to_delegation(self) -> None:
        """User role maps to DELEGATION message type."""
        a2a = A2AMessage(
            role=A2AMessageRole.USER,
            parts=(A2ATextPart(text="do this"),),
        )
        msg = from_a2a(
            a2a,
            channel="test",
            sender="external",
            recipient="internal",
        )
        assert msg.type == MessageType.DELEGATION

    @pytest.mark.unit
    def test_agent_role_maps_to_task_update(self) -> None:
        """Agent role maps to TASK_UPDATE message type."""
        a2a = A2AMessage(
            role=A2AMessageRole.AGENT,
            parts=(A2ATextPart(text="done"),),
        )
        msg = from_a2a(
            a2a,
            channel="test",
            sender="external",
            recipient="internal",
        )
        assert msg.type == MessageType.TASK_UPDATE

    @pytest.mark.unit
    def test_sender_and_recipient_set(self) -> None:
        """Sender and recipient are set from args."""
        a2a = A2AMessage(
            role=A2AMessageRole.USER,
            parts=(A2ATextPart(text="test"),),
        )
        msg = from_a2a(
            a2a,
            channel="ch-1",
            sender="peer-a",
            recipient="agent-x",
        )
        assert msg.sender == "peer-a"
        assert msg.to == "agent-x"
        assert msg.channel == "ch-1"

    @pytest.mark.unit
    def test_data_part_round_trip(self) -> None:
        """DataPart survives A2A round-trip."""
        a2a = A2AMessage(
            role=A2AMessageRole.AGENT,
            parts=(A2ADataPart(data={"result": [1, 2, 3]}),),
        )
        msg = from_a2a(
            a2a,
            channel="test",
            sender="s",
            recipient="r",
        )
        assert isinstance(msg.parts[0], DataPart)

    @pytest.mark.unit
    def test_file_part_round_trip(self) -> None:
        """FilePart survives A2A round-trip."""
        a2a = A2AMessage(
            role=A2AMessageRole.AGENT,
            parts=(
                A2AFilePart(
                    uri="https://example.com/file.txt",
                    mime_type="text/plain",
                ),
            ),
        )
        msg = from_a2a(
            a2a,
            channel="test",
            sender="s",
            recipient="r",
        )
        assert isinstance(msg.parts[0], FilePart)
        assert msg.parts[0].uri == "https://example.com/file.txt"
