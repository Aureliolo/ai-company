"""Communication domain models for the AI company framework."""

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
    AttachmentType,
    ChannelType,
    CommunicationPattern,
    MessageBusBackend,
    MessagePriority,
    MessageType,
)
from ai_company.communication.message import Attachment, Message, MessageMetadata

__all__ = [
    "Attachment",
    "AttachmentType",
    "Channel",
    "ChannelType",
    "CircuitBreakerConfig",
    "CommunicationConfig",
    "CommunicationPattern",
    "HierarchyConfig",
    "LoopPreventionConfig",
    "MeetingTypeConfig",
    "MeetingsConfig",
    "Message",
    "MessageBusBackend",
    "MessageBusConfig",
    "MessageMetadata",
    "MessagePriority",
    "MessageType",
    "RateLimitConfig",
]
