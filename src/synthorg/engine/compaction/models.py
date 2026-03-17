"""Compaction configuration and result models.

All models are frozen Pydantic models following the project's
immutability convention.
"""

from pydantic import BaseModel, ConfigDict, Field


class CompactionConfig(BaseModel):
    """Configuration for context compaction behavior.

    Attributes:
        fill_threshold_percent: Context fill percentage that triggers
            compaction (e.g. 80.0 means compact when 80% full).
        min_messages_to_compact: Minimum number of conversation
            messages required before compaction is allowed.
        preserve_recent_turns: Number of recent turn pairs to keep
            uncompressed after compaction.
    """

    model_config = ConfigDict(frozen=True)

    fill_threshold_percent: float = Field(
        default=80.0,
        gt=0.0,
        le=100.0,
        description="Fill percentage that triggers compaction",
    )
    min_messages_to_compact: int = Field(
        default=4,
        ge=2,
        description="Minimum messages before compaction is allowed",
    )
    preserve_recent_turns: int = Field(
        default=3,
        ge=1,
        description="Recent turn pairs to keep uncompressed",
    )


class CompressionMetadata(BaseModel):
    """Metadata about conversation compression on an ``AgentContext``.

    Attached to ``AgentContext.compression_metadata`` when conversation
    compaction has occurred, enabling compressed checkpoint recovery.

    Attributes:
        compression_point: Turn number at which compaction occurred.
        archived_turns: Number of turns that were archived.
        summary_tokens: Token count of the summary message.
        compactions_performed: Total number of compactions so far.
    """

    model_config = ConfigDict(frozen=True)

    compression_point: int = Field(
        ge=0,
        description="Turn number at which compaction occurred",
    )
    archived_turns: int = Field(
        ge=0,
        description="Number of turns archived",
    )
    summary_tokens: int = Field(
        ge=0,
        description="Token count of the summary message",
    )
    compactions_performed: int = Field(
        default=1,
        ge=1,
        description="Total compactions performed so far",
    )
