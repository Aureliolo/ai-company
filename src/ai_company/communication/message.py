"""Message domain models (DESIGN_SPEC Section 5.3)."""

from collections import Counter
from datetime import datetime  # noqa: TC003
from typing import Self
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ai_company.communication.enums import (
    AttachmentType,
    MessagePriority,
    MessageType,
)


class Attachment(BaseModel):
    """A reference attached to a message.

    Attributes:
        type: The kind of attachment.
        ref: Reference identifier (e.g. artifact ID, URL, file path).
    """

    model_config = ConfigDict(frozen=True)

    type: AttachmentType = Field(description="Kind of attachment")
    ref: str = Field(min_length=1, description="Reference identifier")

    @model_validator(mode="after")
    def _validate_ref_not_blank(self) -> Self:
        """Ensure ref is not whitespace-only."""
        if not self.ref.strip():
            msg = "ref must not be whitespace-only"
            raise ValueError(msg)
        return self


class MessageMetadata(BaseModel):
    """Optional metadata carried with a message.

    Attributes:
        task_id: Related task identifier.
        project_id: Related project identifier.
        tokens_used: LLM tokens consumed producing the message.
        cost_usd: Estimated USD cost of the message.
        extra: Immutable key-value pairs for arbitrary metadata.
    """

    model_config = ConfigDict(frozen=True)

    task_id: str | None = Field(
        default=None,
        min_length=1,
        description="Related task identifier",
    )
    project_id: str | None = Field(
        default=None,
        min_length=1,
        description="Related project identifier",
    )
    tokens_used: int | None = Field(
        default=None,
        ge=0,
        description="LLM tokens consumed",
    )
    cost_usd: float | None = Field(
        default=None,
        ge=0.0,
        description="Estimated USD cost",
    )
    extra: tuple[tuple[str, str], ...] = Field(
        default=(),
        description="Immutable key-value pairs for arbitrary metadata",
    )

    @model_validator(mode="after")
    def _validate_optional_strings(self) -> Self:
        """Ensure optional string fields are not whitespace-only."""
        for field_name in ("task_id", "project_id"):
            value = getattr(self, field_name)
            if value is not None and not value.strip():
                msg = f"{field_name} must not be whitespace-only"
                raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _validate_extra(self) -> Self:
        """Ensure extra keys are non-blank and unique."""
        keys: list[str] = []
        for key, _value in self.extra:
            if not key.strip():
                msg = "extra keys must not be blank"
                raise ValueError(msg)
            keys.append(key)
        if len(keys) != len(set(keys)):
            dupes = sorted(k for k, c in Counter(keys).items() if c > 1)
            msg = f"Duplicate keys in extra: {dupes}"
            raise ValueError(msg)
        return self


class Message(BaseModel):
    """An inter-agent message.

    Field schema matches DESIGN_SPEC Section 5.3.  The ``sender`` field
    is aliased to ``"from"`` for JSON compatibility with the spec format.

    Attributes:
        id: Unique message identifier.
        timestamp: When the message was created.
        sender: Agent ID of the sender (aliased to ``"from"`` in JSON).
        to: Recipient agent or channel identifier.
        type: Message type classification.
        priority: Message priority level.
        channel: Channel the message is sent through.
        content: Message body text.
        attachments: Attached references.
        metadata: Optional message metadata.
    """

    model_config = ConfigDict(frozen=True, populate_by_name=True)

    id: UUID = Field(
        default_factory=uuid4,
        description="Unique message identifier",
    )
    timestamp: datetime = Field(description="When the message was created")
    sender: str = Field(
        min_length=1,
        alias="from",
        description="Sender agent ID",
    )
    to: str = Field(min_length=1, description="Recipient agent or channel")
    type: MessageType = Field(description="Message type classification")
    priority: MessagePriority = Field(
        default=MessagePriority.NORMAL,
        description="Message priority level",
    )
    channel: str = Field(
        min_length=1,
        description="Channel the message is sent through",
    )
    content: str = Field(min_length=1, description="Message body text")
    attachments: tuple[Attachment, ...] = Field(
        default=(),
        description="Attached references",
    )
    metadata: MessageMetadata = Field(
        default_factory=MessageMetadata,
        description="Optional message metadata",
    )

    @model_validator(mode="after")
    def _validate_strings_not_blank(self) -> Self:
        """Ensure required string fields are not whitespace-only."""
        for field_name in ("sender", "to", "channel", "content"):
            if not getattr(self, field_name).strip():
                msg = f"{field_name} must not be whitespace-only"
                raise ValueError(msg)
        return self
