"""Unit test configuration and fixtures for communication models."""

from datetime import UTC, datetime

import pytest
from polyfactory.factories.pydantic_factory import ModelFactory

from ai_company.communication.channel import Channel
from ai_company.communication.config import (
    CircuitBreakerConfig,
    CommunicationConfig,
    HierarchyConfig,
    LoopPreventionConfig,
    MeetingsConfig,
    MeetingTypeConfig,
    MessageBusConfig,
    RateLimitConfig,
)
from ai_company.communication.enums import (
    ChannelType,
    MessagePriority,
    MessageType,
)
from ai_company.communication.message import Attachment, Message, MessageMetadata

# ── Factories ──────────────────────────────────────────────────────


class AttachmentFactory(ModelFactory):
    __model__ = Attachment


class MessageMetadataFactory(ModelFactory):
    __model__ = MessageMetadata
    task_id = None
    project_id = None
    tokens_used = None
    cost_usd = None
    extra = ()


class MessageFactory(ModelFactory):
    __model__ = Message
    priority = MessagePriority.NORMAL
    attachments = ()
    metadata = MessageMetadataFactory


class ChannelFactory(ModelFactory):
    __model__ = Channel
    type = ChannelType.TOPIC
    subscribers = ()


class MessageBusConfigFactory(ModelFactory):
    __model__ = MessageBusConfig


class MeetingTypeConfigFactory(ModelFactory):
    __model__ = MeetingTypeConfig
    frequency = "daily"
    trigger = None


class MeetingsConfigFactory(ModelFactory):
    __model__ = MeetingsConfig
    types = ()


class HierarchyConfigFactory(ModelFactory):
    __model__ = HierarchyConfig


class RateLimitConfigFactory(ModelFactory):
    __model__ = RateLimitConfig


class CircuitBreakerConfigFactory(ModelFactory):
    __model__ = CircuitBreakerConfig


class LoopPreventionConfigFactory(ModelFactory):
    __model__ = LoopPreventionConfig
    ancestry_tracking = True


class CommunicationConfigFactory(ModelFactory):
    __model__ = CommunicationConfig
    meetings = MeetingsConfigFactory
    loop_prevention = LoopPreventionConfigFactory


# ── Sample Fixtures ────────────────────────────────────────────────


@pytest.fixture
def sample_attachment() -> Attachment:
    return Attachment(type="artifact", ref="pr-42")


@pytest.fixture
def sample_metadata() -> MessageMetadata:
    return MessageMetadata(
        task_id="task-123",
        project_id="proj-456",
        tokens_used=1200,
        cost_usd=0.018,
    )


@pytest.fixture
def sample_message(sample_metadata: MessageMetadata) -> Message:
    return Message(
        timestamp=datetime(2026, 2, 27, 10, 30, tzinfo=UTC),
        sender="sarah_chen",
        to="engineering",
        type=MessageType.TASK_UPDATE,
        priority=MessagePriority.NORMAL,
        channel="#backend",
        content="Completed API endpoint for user authentication.",
        attachments=(Attachment(type="artifact", ref="pr-42"),),
        metadata=sample_metadata,
    )


@pytest.fixture
def sample_channel() -> Channel:
    return Channel(
        name="#engineering",
        type=ChannelType.TOPIC,
        subscribers=("sarah_chen", "backend_lead"),
    )


@pytest.fixture
def sample_meeting_type() -> MeetingTypeConfig:
    return MeetingTypeConfig(
        name="daily_standup",
        frequency="per_sprint_day",
        participants=("engineering", "qa"),
        duration_tokens=2000,
    )


@pytest.fixture
def sample_communication_config() -> CommunicationConfig:
    return CommunicationConfig()
