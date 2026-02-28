"""Tests for the communication domain enumerations."""

import pytest

from ai_company.communication.enums import (
    AttachmentType,
    ChannelType,
    CommunicationPattern,
    MessageBusBackend,
    MessagePriority,
    MessageType,
)

pytestmark = pytest.mark.timeout(30)


@pytest.mark.unit
class TestMessageType:
    def test_member_count(self) -> None:
        assert len(MessageType) == 8

    def test_values(self) -> None:
        assert MessageType.TASK_UPDATE == "task_update"
        assert MessageType.QUESTION == "question"
        assert MessageType.ANNOUNCEMENT == "announcement"
        assert MessageType.REVIEW_REQUEST == "review_request"
        assert MessageType.APPROVAL == "approval"
        assert MessageType.DELEGATION == "delegation"
        assert MessageType.STATUS_REPORT == "status_report"
        assert MessageType.ESCALATION == "escalation"

    def test_string_identity(self) -> None:
        assert str(MessageType.TASK_UPDATE) == "task_update"


@pytest.mark.unit
class TestMessagePriority:
    def test_member_count(self) -> None:
        assert len(MessagePriority) == 4

    def test_values(self) -> None:
        assert MessagePriority.LOW == "low"
        assert MessagePriority.NORMAL == "normal"
        assert MessagePriority.HIGH == "high"
        assert MessagePriority.URGENT == "urgent"

    def test_normal_not_medium(self) -> None:
        """Message priority uses 'normal', not 'medium' like task Priority."""
        member_values = {m.value for m in MessagePriority}
        assert "normal" in member_values
        assert "medium" not in member_values


@pytest.mark.unit
class TestChannelType:
    def test_member_count(self) -> None:
        assert len(ChannelType) == 3

    def test_values(self) -> None:
        assert ChannelType.TOPIC == "topic"
        assert ChannelType.DIRECT == "direct"
        assert ChannelType.BROADCAST == "broadcast"


@pytest.mark.unit
class TestAttachmentType:
    def test_member_count(self) -> None:
        assert len(AttachmentType) == 3

    def test_values(self) -> None:
        assert AttachmentType.ARTIFACT == "artifact"
        assert AttachmentType.FILE == "file"
        assert AttachmentType.LINK == "link"


@pytest.mark.unit
class TestCommunicationPattern:
    def test_member_count(self) -> None:
        assert len(CommunicationPattern) == 4

    def test_values(self) -> None:
        assert CommunicationPattern.EVENT_DRIVEN == "event_driven"
        assert CommunicationPattern.HIERARCHICAL == "hierarchical"
        assert CommunicationPattern.MEETING_BASED == "meeting_based"
        assert CommunicationPattern.HYBRID == "hybrid"


@pytest.mark.unit
class TestCommunicationExports:
    def test_all_exports_importable(self) -> None:
        import ai_company.communication as comm_module

        for name in comm_module.__all__:
            assert hasattr(comm_module, name), f"{name} in __all__ but not importable"


@pytest.mark.unit
class TestMessageBusBackend:
    def test_member_count(self) -> None:
        assert len(MessageBusBackend) == 4

    def test_values(self) -> None:
        assert MessageBusBackend.INTERNAL == "internal"
        assert MessageBusBackend.REDIS == "redis"
        assert MessageBusBackend.RABBITMQ == "rabbitmq"
        assert MessageBusBackend.KAFKA == "kafka"
