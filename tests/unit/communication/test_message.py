"""Tests for the Part, MessageMetadata, and Message domain models."""

from datetime import UTC, datetime
from types import MappingProxyType
from uuid import UUID

import pytest
from pydantic import ValidationError

from synthorg.communication.enums import (
    MessagePriority,
    MessageType,
)
from synthorg.communication.message import (
    DataPart,
    FilePart,
    Message,
    MessageMetadata,
    TextPart,
    UriPart,
)

# ── Helpers ──────────────────────────────────────────────────────

_MESSAGE_KWARGS: dict[str, object] = {
    "timestamp": datetime(2026, 2, 27, 10, 30, tzinfo=UTC),
    "sender": "sarah_chen",
    "to": "engineering",
    "type": MessageType.TASK_UPDATE,
    "channel": "#backend",
    "parts": (TextPart(text="PR ready for review."),),
}


def _make_message(**overrides: object) -> Message:
    """Create a Message with sensible defaults, applying overrides."""
    kwargs = {**_MESSAGE_KWARGS, **overrides}
    return Message(**kwargs)  # type: ignore[arg-type]


# ── TextPart ─────────────────────────────────────────────────────


@pytest.mark.unit
class TestTextPart:
    def test_construction(self) -> None:
        part = TextPart(text="Hello, world!")
        assert part.type == "text"
        assert part.text == "Hello, world!"

    def test_empty_text_rejected(self) -> None:
        with pytest.raises(ValidationError):
            TextPart(text="")

    def test_whitespace_text_rejected(self) -> None:
        with pytest.raises(ValidationError, match="whitespace-only"):
            TextPart(text="   ")

    def test_frozen(self) -> None:
        part = TextPart(text="Original")
        with pytest.raises(ValidationError):
            part.text = "Modified"  # type: ignore[misc]

    def test_json_roundtrip(self) -> None:
        part = TextPart(text="Hello")
        restored = TextPart.model_validate_json(part.model_dump_json())
        assert restored == part

    def test_model_dump(self) -> None:
        part = TextPart(text="Content")
        dumped = part.model_dump()
        assert dumped["type"] == "text"
        assert dumped["text"] == "Content"

    def test_model_copy(self) -> None:
        original = TextPart(text="Original")
        updated = original.model_copy(update={"text": "Updated"})
        assert updated.text == "Updated"
        assert original.text == "Original"


# ── DataPart ─────────────────────────────────────────────────────


@pytest.mark.unit
class TestDataPart:
    def test_construction(self) -> None:
        data = {"key": "value", "count": 42}
        part = DataPart(data=data)  # type: ignore[arg-type]
        assert part.type == "data"
        assert isinstance(part.data, MappingProxyType)
        assert part.data["key"] == "value"
        assert part.data["count"] == 42

    def test_frozen(self) -> None:
        part = DataPart(data={"key": "value"})  # type: ignore[arg-type]
        with pytest.raises(ValidationError):
            part.data = {}  # type: ignore[misc,assignment]

    def test_data_deep_copied(self) -> None:
        original_dict = {"key": "value"}
        part = DataPart(data=original_dict)  # type: ignore[arg-type]
        original_dict["key"] = "modified"
        assert part.data["key"] == "value"

    def test_data_recursively_frozen(self) -> None:
        data = {
            "nested": {"inner": "value"},
            "list": [1, 2, 3],
        }
        part = DataPart(data=data)  # type: ignore[arg-type]
        assert isinstance(part.data["nested"], MappingProxyType)
        assert isinstance(part.data["list"], tuple)

    def test_json_roundtrip(self) -> None:
        part = DataPart(data={"key": "value", "num": 123})  # type: ignore[arg-type]
        restored = DataPart.model_validate_json(part.model_dump_json())
        assert restored.data["key"] == "value"
        assert restored.data["num"] == 123

    def test_model_copy(self) -> None:
        original = DataPart(data={"key": "value"})  # type: ignore[arg-type]
        updated = original.model_copy(update={"data": {"key": "new"}})
        assert updated.data["key"] == "new"
        assert original.data["key"] == "value"


# ── FilePart ─────────────────────────────────────────────────────


@pytest.mark.unit
class TestFilePart:
    def test_construction_with_mime_type(self) -> None:
        part = FilePart(uri="/path/to/file.pdf", mime_type="application/pdf")
        assert part.type == "file"
        assert part.uri == "/path/to/file.pdf"
        assert part.mime_type == "application/pdf"

    def test_construction_without_mime_type(self) -> None:
        part = FilePart(uri="/path/to/file.txt")
        assert part.type == "file"
        assert part.uri == "/path/to/file.txt"
        assert part.mime_type is None

    def test_empty_uri_rejected(self) -> None:
        with pytest.raises(ValidationError):
            FilePart(uri="", mime_type="text/plain")

    def test_whitespace_uri_rejected(self) -> None:
        with pytest.raises(ValidationError, match="whitespace-only"):
            FilePart(uri="   ", mime_type="text/plain")

    def test_empty_mime_type_rejected(self) -> None:
        with pytest.raises(ValidationError):
            FilePart(uri="/file.txt", mime_type="")

    def test_whitespace_mime_type_rejected(self) -> None:
        with pytest.raises(ValidationError, match="whitespace-only"):
            FilePart(uri="/file.txt", mime_type="   ")

    def test_frozen(self) -> None:
        part = FilePart(uri="/file.txt", mime_type="text/plain")
        with pytest.raises(ValidationError):
            part.uri = "/other.txt"  # type: ignore[misc]

    def test_json_roundtrip(self) -> None:
        part = FilePart(uri="/file.pdf", mime_type="application/pdf")
        restored = FilePart.model_validate_json(part.model_dump_json())
        assert restored == part

    def test_model_dump(self) -> None:
        part = FilePart(uri="/file.txt", mime_type="text/plain")
        dumped = part.model_dump()
        assert dumped["type"] == "file"
        assert dumped["uri"] == "/file.txt"
        assert dumped["mime_type"] == "text/plain"

    def test_model_copy(self) -> None:
        original = FilePart(uri="/file.txt", mime_type="text/plain")
        updated = original.model_copy(update={"uri": "/other.txt"})
        assert updated.uri == "/other.txt"
        assert original.uri == "/file.txt"


# ── UriPart ──────────────────────────────────────────────────────


@pytest.mark.unit
class TestUriPart:
    def test_construction(self) -> None:
        part = UriPart(uri="https://example.com/page")
        assert part.type == "uri"
        assert part.uri == "https://example.com/page"

    def test_empty_uri_rejected(self) -> None:
        with pytest.raises(ValidationError):
            UriPart(uri="")

    def test_whitespace_uri_rejected(self) -> None:
        with pytest.raises(ValidationError, match="whitespace-only"):
            UriPart(uri="   ")

    def test_frozen(self) -> None:
        part = UriPart(uri="https://example.com")
        with pytest.raises(ValidationError):
            part.uri = "https://other.com"  # type: ignore[misc]

    def test_json_roundtrip(self) -> None:
        part = UriPart(uri="https://example.com")
        restored = UriPart.model_validate_json(part.model_dump_json())
        assert restored == part

    def test_model_dump(self) -> None:
        part = UriPart(uri="https://example.com")
        dumped = part.model_dump()
        assert dumped["type"] == "uri"
        assert dumped["uri"] == "https://example.com"

    def test_model_copy(self) -> None:
        original = UriPart(uri="https://example.com")
        updated = original.model_copy(update={"uri": "https://other.com"})
        assert updated.uri == "https://other.com"
        assert original.uri == "https://example.com"


# ── MessageMetadata ─────────────────────────────────────────────


@pytest.mark.unit
class TestMessageMetadataDefaults:
    def test_defaults(self) -> None:
        meta = MessageMetadata()
        assert meta.task_id is None
        assert meta.project_id is None
        assert meta.tokens_used is None
        assert meta.cost is None
        assert meta.extra == ()

    def test_custom_values(self) -> None:
        meta = MessageMetadata(
            task_id="task-1",
            project_id="proj-1",
            tokens_used=500,
            cost=0.05,
            extra=(("key1", "val1"),),
        )
        assert meta.task_id == "task-1"
        assert meta.project_id == "proj-1"
        assert meta.tokens_used == 500
        assert meta.cost == 0.05
        assert meta.extra == (("key1", "val1"),)


@pytest.mark.unit
class TestMessageMetadataValidation:
    def test_empty_task_id_rejected(self) -> None:
        with pytest.raises(ValidationError):
            MessageMetadata(task_id="")

    def test_whitespace_task_id_rejected(self) -> None:
        with pytest.raises(ValidationError, match="whitespace-only"):
            MessageMetadata(task_id="   ")

    def test_empty_project_id_rejected(self) -> None:
        with pytest.raises(ValidationError):
            MessageMetadata(project_id="")

    def test_whitespace_project_id_rejected(self) -> None:
        with pytest.raises(ValidationError, match="whitespace-only"):
            MessageMetadata(project_id="   ")

    def test_negative_tokens_rejected(self) -> None:
        with pytest.raises(ValidationError):
            MessageMetadata(tokens_used=-1)

    def test_negative_cost_rejected(self) -> None:
        with pytest.raises(ValidationError):
            MessageMetadata(cost=-0.01)

    def test_zero_tokens_allowed(self) -> None:
        meta = MessageMetadata(tokens_used=0)
        assert meta.tokens_used == 0

    def test_zero_cost_allowed(self) -> None:
        meta = MessageMetadata(cost=0.0)
        assert meta.cost == 0.0

    def test_blank_extra_key_rejected(self) -> None:
        with pytest.raises(ValidationError, match="extra keys must not be blank"):
            MessageMetadata(extra=(("  ", "val"),))

    def test_duplicate_extra_keys_rejected(self) -> None:
        with pytest.raises(ValidationError, match="Duplicate keys in extra"):
            MessageMetadata(extra=(("k", "v1"), ("k", "v2")))


@pytest.mark.unit
class TestMessageMetadataImmutability:
    def test_frozen(self) -> None:
        meta = MessageMetadata(task_id="task-1")
        with pytest.raises(ValidationError):
            meta.task_id = "task-2"  # type: ignore[misc]

    def test_model_copy(self) -> None:
        original = MessageMetadata(task_id="task-1")
        updated = original.model_copy(update={"task_id": "task-2"})
        assert updated.task_id == "task-2"
        assert original.task_id == "task-1"


@pytest.mark.unit
class TestMessageMetadataSerialization:
    def test_json_roundtrip(self) -> None:
        meta = MessageMetadata(
            task_id="task-1",
            project_id="proj-1",
            tokens_used=100,
            cost=0.01,
            extra=(("env", "prod"),),
        )
        restored = MessageMetadata.model_validate_json(meta.model_dump_json())
        assert restored == meta

    def test_factory(self) -> None:
        from tests.unit.communication.conftest import MessageMetadataFactory

        meta = MessageMetadataFactory.build()
        assert isinstance(meta, MessageMetadata)


# ── Message ──────────────────────────────────────────────────────


@pytest.mark.unit
class TestMessageConstruction:
    def test_minimal_valid(self) -> None:
        msg = _make_message()
        assert isinstance(msg.id, UUID)
        assert msg.sender == "sarah_chen"
        assert msg.to == "engineering"
        assert msg.type is MessageType.TASK_UPDATE
        assert msg.channel == "#backend"
        assert msg.text == "PR ready for review."

    def test_default_values(self) -> None:
        msg = _make_message()
        assert msg.priority is MessagePriority.NORMAL
        assert isinstance(msg.metadata, MessageMetadata)

    def test_all_fields_set(self) -> None:
        meta = MessageMetadata(task_id="task-1")
        msg = Message(
            timestamp=datetime(2026, 2, 27, 10, 30, tzinfo=UTC),
            sender="sarah_chen",
            to="engineering",
            type=MessageType.REVIEW_REQUEST,
            priority=MessagePriority.HIGH,
            channel="#code-review",
            parts=(TextPart(text="Please review PR-42."),),
            metadata=meta,
        )
        assert msg.priority is MessagePriority.HIGH
        assert len(msg.parts) == 1
        assert msg.metadata.task_id == "task-1"

    def test_multiple_parts(self) -> None:
        msg = Message(
            timestamp=datetime(2026, 2, 27, 10, 30, tzinfo=UTC),
            sender="alice",
            to="bob",
            type=MessageType.TASK_UPDATE,
            channel="#general",
            parts=(
                TextPart(text="Status update:"),
                DataPart(data={"status": "complete", "progress": 100}),  # type: ignore[arg-type]
                UriPart(uri="https://example.com/report"),
            ),
        )
        assert len(msg.parts) == 3
        assert isinstance(msg.parts[0], TextPart)
        assert isinstance(msg.parts[1], DataPart)
        assert isinstance(msg.parts[2], UriPart)


@pytest.mark.unit
class TestMessageTextComputedField:
    def test_text_from_first_text_part(self) -> None:
        msg = Message(
            timestamp=datetime(2026, 2, 27, 10, 30, tzinfo=UTC),
            sender="alice",
            to="bob",
            type=MessageType.TASK_UPDATE,
            channel="#general",
            parts=(
                TextPart(text="Primary message"),
                DataPart(data={"key": "value"}),  # type: ignore[arg-type]
            ),
        )
        assert msg.text == "Primary message"

    def test_text_empty_when_no_text_part(self) -> None:
        msg = Message(
            timestamp=datetime(2026, 2, 27, 10, 30, tzinfo=UTC),
            sender="alice",
            to="bob",
            type=MessageType.TASK_UPDATE,
            channel="#general",
            parts=(
                DataPart(data={"key": "value"}),  # type: ignore[arg-type]
                UriPart(uri="https://example.com"),
            ),
        )
        assert msg.text == ""

    def test_text_skips_non_text_parts(self) -> None:
        msg = Message(
            timestamp=datetime(2026, 2, 27, 10, 30, tzinfo=UTC),
            sender="alice",
            to="bob",
            type=MessageType.TASK_UPDATE,
            channel="#general",
            parts=(
                UriPart(uri="https://example.com"),
                TextPart(text="Secondary text"),
            ),
        )
        assert msg.text == "Secondary text"


@pytest.mark.unit
class TestMessagePartsValidation:
    def test_empty_parts_rejected(self) -> None:
        with pytest.raises(ValidationError, match="too_short"):
            Message(
                timestamp=datetime(2026, 2, 27, 10, 30, tzinfo=UTC),
                sender="alice",
                to="bob",
                type=MessageType.TASK_UPDATE,
                channel="#general",
                parts=(),
            )


@pytest.mark.unit
class TestMessageUniqueIds:
    def test_unique_ids(self) -> None:
        msg1 = _make_message()
        msg2 = _make_message()
        assert msg1.id != msg2.id


@pytest.mark.unit
class TestMessageAlias:
    def test_alias_from_parsing(self) -> None:
        """Parse JSON with 'from' key (DESIGN_SPEC 5.3 format)."""
        data = {
            "timestamp": "2026-02-27T10:30:00Z",
            "from": "sarah_chen",
            "to": "engineering",
            "type": "task_update",
            "channel": "#backend",
            "parts": [{"type": "text", "text": "Hello."}],
        }
        msg = Message.model_validate(data)
        assert msg.sender == "sarah_chen"

    def test_populate_by_name(self) -> None:
        """Parse JSON with 'sender' key (populate_by_name=True)."""
        data = {
            "timestamp": "2026-02-27T10:30:00Z",
            "sender": "sarah_chen",
            "to": "engineering",
            "type": "task_update",
            "channel": "#backend",
            "parts": [{"type": "text", "text": "Hello."}],
        }
        msg = Message.model_validate(data)
        assert msg.sender == "sarah_chen"

    def test_dump_by_alias(self) -> None:
        """model_dump(by_alias=True) outputs 'from' key."""
        msg = _make_message()
        dumped = msg.model_dump(by_alias=True)
        assert "from" in dumped
        assert dumped["from"] == "sarah_chen"

    def test_dump_by_name(self) -> None:
        """model_dump() outputs 'sender' key."""
        msg = _make_message()
        dumped = msg.model_dump()
        assert "sender" in dumped
        assert dumped["sender"] == "sarah_chen"


@pytest.mark.unit
class TestMessageAliasRoundtrip:
    def test_json_roundtrip_with_alias(self) -> None:
        """Ensure JSON with 'from' key (DESIGN_SPEC 5.3 format) round-trips."""
        msg = _make_message()
        json_str = msg.model_dump_json(by_alias=True)
        assert '"from"' in json_str
        restored = Message.model_validate_json(json_str)
        assert restored == msg


@pytest.mark.unit
class TestMessageStringValidation:
    def test_empty_sender_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _make_message(sender="")

    def test_whitespace_sender_rejected(self) -> None:
        with pytest.raises(ValidationError, match="whitespace-only"):
            _make_message(sender="   ")

    def test_empty_to_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _make_message(to="")

    def test_whitespace_to_rejected(self) -> None:
        with pytest.raises(ValidationError, match="whitespace-only"):
            _make_message(to="   ")

    def test_empty_channel_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _make_message(channel="")

    def test_whitespace_channel_rejected(self) -> None:
        with pytest.raises(ValidationError, match="whitespace-only"):
            _make_message(channel="   ")


@pytest.mark.unit
class TestMessageImmutability:
    def test_frozen(self) -> None:
        msg = _make_message()
        with pytest.raises(ValidationError):
            msg.parts = (TextPart(text="new"),)  # type: ignore[misc]

    def test_model_copy(self) -> None:
        original = _make_message()
        updated = original.model_copy(
            update={"parts": (TextPart(text="Updated content."),)}
        )
        assert updated.text == "Updated content."
        assert original.text == "PR ready for review."


@pytest.mark.unit
class TestMessageSerialization:
    def test_json_roundtrip_with_text_part(self) -> None:
        msg = _make_message(
            metadata=MessageMetadata(task_id="task-1"),
        )
        json_str = msg.model_dump_json()
        restored = Message.model_validate_json(json_str)
        assert restored.id == msg.id
        assert restored.sender == msg.sender
        assert restored.type is msg.type
        assert restored.text == msg.text
        assert restored.metadata == msg.metadata

    def test_json_roundtrip_with_multiple_parts(self) -> None:
        msg = Message(
            timestamp=datetime(2026, 2, 27, 10, 30, tzinfo=UTC),
            sender="alice",
            to="bob",
            type=MessageType.TASK_UPDATE,
            channel="#general",
            parts=(
                TextPart(text="Status:"),
                DataPart(data={"status": "done"}),  # type: ignore[arg-type]
                FilePart(uri="/report.pdf", mime_type="application/pdf"),
            ),
            metadata=MessageMetadata(task_id="task-1"),
        )
        json_str = msg.model_dump_json()
        restored = Message.model_validate_json(json_str)
        assert restored.id == msg.id
        assert len(restored.parts) == 3
        assert isinstance(restored.parts[0], TextPart)
        assert isinstance(restored.parts[1], DataPart)
        assert isinstance(restored.parts[2], FilePart)

    def test_parts_discriminator_roundtrip(self) -> None:
        """Verify that the 'type' discriminator correctly routes deserialization."""
        msg = Message(
            timestamp=datetime(2026, 2, 27, 10, 30, tzinfo=UTC),
            sender="alice",
            to="bob",
            type=MessageType.TASK_UPDATE,
            channel="#general",
            parts=(
                TextPart(text="Text"),
                DataPart(data={"k": "v"}),  # type: ignore[arg-type]
                FilePart(uri="/file.txt"),
                UriPart(uri="https://example.com"),
            ),
        )
        dumped = msg.model_dump()
        restored = Message.model_validate(dumped)
        assert isinstance(restored.parts[0], TextPart)
        assert isinstance(restored.parts[1], DataPart)
        assert isinstance(restored.parts[2], FilePart)
        assert isinstance(restored.parts[3], UriPart)

    def test_model_dump_enum_values(self) -> None:
        msg = _make_message()
        dumped = msg.model_dump()
        assert dumped["type"] == "task_update"
        assert dumped["priority"] == "normal"


@pytest.mark.unit
class TestMessageFactory:
    def test_factory(self) -> None:
        from tests.unit.communication.conftest import MessageFactory

        msg = MessageFactory.build()
        assert isinstance(msg, Message)
        assert isinstance(msg.id, UUID)
        assert isinstance(msg.type, MessageType)


@pytest.mark.unit
class TestMessageFixtures:
    def test_sample_message(self, sample_message: Message) -> None:
        assert sample_message.sender == "sarah_chen"
        assert sample_message.to == "engineering"
        assert sample_message.type is MessageType.TASK_UPDATE
        assert len(sample_message.parts) >= 1

    def test_sample_metadata(self, sample_metadata: MessageMetadata) -> None:
        assert sample_metadata.task_id == "task-123"
        assert sample_metadata.tokens_used == 1200
