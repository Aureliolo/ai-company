"""Cost record model for per-API-call tracking.

Implements the Cost Tracking section of the Operations design page:
every API call is tracked as an immutable cost record
(append-only pattern).
"""

from typing import Self

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from synthorg.budget.call_category import LLMCallCategory  # noqa: TC001
from synthorg.core.types import NotBlankStr  # noqa: TC001
from synthorg.providers.enums import FinishReason  # noqa: TC001


class CostRecord(BaseModel):
    """Immutable record of a single API call's cost.

    Once created, a ``CostRecord`` cannot be modified (frozen model).
    This enforces the append-only pattern: new records are created for
    each API call; existing records are never updated.

    Attributes:
        agent_id: Agent identifier (string reference).
        task_id: Task identifier (string reference).
        provider: LLM provider name.
        model: Model identifier.
        input_tokens: Input token count.
        output_tokens: Output token count.
        cost_usd: Cost in USD (base currency).
        timestamp: Timezone-aware timestamp of the API call.
        call_category: Optional LLM call category (productive,
            coordination, system, embedding).
        accuracy_effort_ratio: Accuracy-effort ratio for the task
            this call belongs to (populated at task completion when
            quality signals are available, ``None`` otherwise).
        latency_ms: Round-trip latency in milliseconds (``None`` if not measured).
        cache_hit: Whether the provider served this call from cache.
        retry_count: Number of retry attempts before success (0 = first try succeeded).
        retry_reason: Exception type name of the last retried error.
        finish_reason: LLM finish reason for this call.
        success: Whether the call completed without error or content filter.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    agent_id: NotBlankStr = Field(description="Agent identifier")
    task_id: NotBlankStr = Field(description="Task identifier")
    provider: NotBlankStr = Field(description="LLM provider name")
    model: NotBlankStr = Field(description="Model identifier")
    input_tokens: int = Field(ge=0, description="Input token count")
    output_tokens: int = Field(ge=0, description="Output token count")
    cost_usd: float = Field(ge=0.0, description="Cost in USD (base currency)")
    timestamp: AwareDatetime = Field(description="Timestamp of the API call")
    call_category: LLMCallCategory | None = Field(
        default=None,
        description="LLM call category (productive, coordination, system, embedding)",
    )
    accuracy_effort_ratio: float | None = Field(
        default=None,
        ge=0.0,
        description=(
            "Accuracy-effort ratio for the task this call belongs to "
            "(populated at task completion when quality signals are available)"
        ),
    )
    latency_ms: float | None = Field(
        default=None,
        ge=0.0,
        description="Round-trip latency in milliseconds",
    )
    cache_hit: bool | None = Field(
        default=None,
        description="Whether the provider served this call from cache",
    )
    retry_count: int | None = Field(
        default=None,
        ge=0,
        description="Number of retry attempts before success",
    )
    retry_reason: str | None = Field(
        default=None,
        description="Exception type name of the last retried error",
    )
    finish_reason: FinishReason | None = Field(
        default=None,
        description="LLM finish reason for this call",
    )
    success: bool | None = Field(
        default=None,
        description="Whether the call completed without error or content filter",
    )

    @model_validator(mode="after")
    def _validate_token_consistency(self) -> Self:
        """Ensure positive cost implies at least one non-zero token count."""
        if self.cost_usd > 0 and self.input_tokens == 0 and self.output_tokens == 0:
            msg = "cost_usd is positive but both token counts are zero"
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _validate_retry_consistency(self) -> Self:
        """Ensure retry_reason and retry_count are consistent.

        If a retry reason is set, at least one retry must have occurred.
        If retry_count is zero or unset, there can be no retry reason.
        """
        if self.retry_reason is not None and (
            self.retry_count is None or self.retry_count == 0
        ):
            msg = "retry_reason set implies retry_count must be >= 1"
            raise ValueError(msg)
        return self
