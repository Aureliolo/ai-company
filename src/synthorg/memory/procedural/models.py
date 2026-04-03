"""Domain models for procedural memory auto-generation.

Defines the failure analysis payload (input to the proposer),
the procedural memory proposal (output from the proposer), and
the configuration model for the procedural memory pipeline.
"""

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from synthorg.core.enums import TaskType  # noqa: TC001
from synthorg.core.types import NotBlankStr  # noqa: TC001


class FailureAnalysisPayload(BaseModel):
    """Structured failure context for the proposer LLM.

    Built from ``RecoveryResult`` and ``ExecutionResult`` fields.
    Deliberately excludes raw conversation messages to maintain
    the privacy boundary established by ``AgentContextSnapshot``.

    Attributes:
        task_id: Failed task identifier.
        task_title: Human-readable task title.
        task_description: Full task description.
        task_type: Task type classification.
        error_message: Error that triggered recovery.
        strategy_type: Recovery strategy used.
        termination_reason: Why the execution loop stopped.
        turn_count: Number of LLM turns completed before failure.
        tool_calls_made: Flattened tool names from all turns.
        retry_count: Previous retry attempts for this task.
        max_retries: Maximum allowed retries.
        can_reassign: Whether the task can be reassigned.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    task_id: NotBlankStr = Field(description="Failed task identifier")
    task_title: NotBlankStr = Field(description="Task title")
    task_description: NotBlankStr = Field(description="Task description")
    task_type: TaskType = Field(description="Task type classification")
    error_message: NotBlankStr = Field(description="Error that triggered recovery")
    strategy_type: NotBlankStr = Field(description="Recovery strategy used")
    termination_reason: NotBlankStr = Field(
        description="Why the execution loop stopped",
    )
    turn_count: int = Field(ge=0, description="LLM turns completed")
    tool_calls_made: tuple[NotBlankStr, ...] = Field(
        default=(),
        description="Flattened tool names from all turns",
    )
    retry_count: int = Field(ge=0, description="Previous retry attempts")
    max_retries: int = Field(ge=0, description="Maximum allowed retries")
    can_reassign: bool = Field(description="Whether task can be reassigned")


class ProceduralMemoryProposal(BaseModel):
    """Structured proposal from the proposer LLM.

    Encodes the three-tier progressive disclosure format:
    ``discovery`` (~100 tokens) for retrieval ranking,
    ``condition`` + ``action`` + ``rationale`` (<5000 tokens)
    for activation-level detail.

    Attributes:
        discovery: Short summary for retrieval ranking (~100 tokens).
        condition: When to apply this procedural knowledge.
        action: What to do differently next time.
        rationale: Why this approach helps.
        confidence: Proposer's confidence in the proposal (0.0-1.0).
        tags: Semantic tags for filtering.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    discovery: NotBlankStr = Field(
        description="Short summary for retrieval ranking",
    )
    condition: NotBlankStr = Field(
        description="When to apply this knowledge",
    )
    action: NotBlankStr = Field(
        description="What to do differently next time",
    )
    rationale: NotBlankStr = Field(
        description="Why this approach helps",
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Proposer confidence (0.0-1.0)",
    )
    tags: tuple[NotBlankStr, ...] = Field(
        default=(),
        description="Semantic tags for filtering",
    )

    @model_validator(mode="after")
    def _deduplicate_tags(self) -> Self:
        """Remove duplicate tags while preserving order."""
        unique = tuple(dict.fromkeys(self.tags))
        if len(unique) != len(self.tags):
            object.__setattr__(self, "tags", unique)
        return self


class ProceduralMemoryConfig(BaseModel):
    """Configuration for procedural memory auto-generation.

    Controls whether the proposer pipeline runs after agent
    failures, which model to use, and quality thresholds.

    Attributes:
        enabled: Whether procedural memory generation is active.
        model: Model identifier for the proposer LLM call.
        temperature: Sampling temperature for the proposer.
        max_tokens: Maximum tokens for the proposer response.
        min_confidence: Discard proposals below this confidence.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    enabled: bool = Field(
        default=True,
        description="Whether procedural memory generation is active",
    )
    model: NotBlankStr = Field(
        default="example-small-001",
        description="Model identifier for the proposer LLM call",
    )
    temperature: float = Field(
        default=0.3,
        ge=0.0,
        le=2.0,
        description="Sampling temperature for the proposer",
    )
    max_tokens: int = Field(
        default=1000,
        gt=0,
        description="Maximum tokens for the proposer response",
    )
    min_confidence: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Discard proposals below this confidence",
    )
