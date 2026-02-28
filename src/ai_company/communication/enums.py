"""Communication domain enumerations."""

from enum import StrEnum


class MessageType(StrEnum):
    """Type of inter-agent message.

    Maps to the ``type`` field in DESIGN_SPEC Section 5.3.
    """

    TASK_UPDATE = "task_update"
    QUESTION = "question"
    ANNOUNCEMENT = "announcement"
    REVIEW_REQUEST = "review_request"
    APPROVAL = "approval"
    DELEGATION = "delegation"
    STATUS_REPORT = "status_report"
    ESCALATION = "escalation"


class MessagePriority(StrEnum):
    """Priority level for messages.

    Separate from :class:`ai_company.core.enums.Priority` which uses
    ``"medium"``; message priority uses ``"normal"`` per DESIGN_SPEC 5.3.
    """

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class ChannelType(StrEnum):
    """Channel delivery semantics.

    Members:
        TOPIC: Publish-subscribe delivery to all subscribers.
        DIRECT: Point-to-point delivery to a single recipient.
        BROADCAST: Delivery to all agents regardless of subscription.
    """

    TOPIC = "topic"
    DIRECT = "direct"
    BROADCAST = "broadcast"


class AttachmentType(StrEnum):
    """Type of message attachment.

    Members:
        ARTIFACT: Reference to a domain artifact (e.g. PR, build output).
        FILE: Reference to a file path.
        LINK: Reference to a URL.
    """

    ARTIFACT = "artifact"
    FILE = "file"
    LINK = "link"


class CommunicationPattern(StrEnum):
    """High-level communication pattern for the company.

    Maps to DESIGN_SPEC Section 5.1.
    """

    EVENT_DRIVEN = "event_driven"
    HIERARCHICAL = "hierarchical"
    MEETING_BASED = "meeting_based"
    HYBRID = "hybrid"


class MessageBusBackend(StrEnum):
    """Message bus backend implementation.

    Maps to DESIGN_SPEC Section 5.4 ``message_bus.backend``.
    """

    INTERNAL = "internal"
    REDIS = "redis"
    RABBITMQ = "rabbitmq"
    KAFKA = "kafka"
