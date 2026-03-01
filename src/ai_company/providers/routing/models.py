"""Domain models for the routing engine."""

from pydantic import BaseModel, ConfigDict, Field

from ai_company.core.enums import SeniorityLevel  # noqa: TC001
from ai_company.core.types import NotBlankStr  # noqa: TC001


class ResolvedModel(BaseModel):
    """A fully resolved model reference.

    Attributes:
        provider_name: Provider that owns this model (e.g. ``"anthropic"``).
        model_id: Concrete model identifier (e.g. ``"claude-sonnet-4-6"``).
        alias: Short alias used in routing rules, if any.
        cost_per_1k_input: Cost per 1 000 input tokens in USD.
        cost_per_1k_output: Cost per 1 000 output tokens in USD.
        max_context: Maximum context window size in tokens.
    """

    model_config = ConfigDict(frozen=True)

    provider_name: NotBlankStr = Field(description="Provider name")
    model_id: NotBlankStr = Field(description="Model identifier")
    alias: str | None = Field(default=None, description="Short alias")
    cost_per_1k_input: float = Field(
        default=0.0,
        ge=0.0,
        description="Cost per 1k input tokens in USD",
    )
    cost_per_1k_output: float = Field(
        default=0.0,
        ge=0.0,
        description="Cost per 1k output tokens in USD",
    )
    max_context: int = Field(
        default=200_000,
        gt=0,
        description="Maximum context window size in tokens",
    )


class RoutingRequest(BaseModel):
    """Inputs to a routing decision.

    Attributes:
        agent_level: Seniority level of the requesting agent.
        task_type: Task type label (e.g. ``"development"``).
        model_override: Explicit model reference for manual routing.
        remaining_budget: Remaining cost budget in USD.
    """

    model_config = ConfigDict(frozen=True)

    agent_level: SeniorityLevel | None = Field(
        default=None,
        description="Seniority level of the requesting agent",
    )
    task_type: str | None = Field(
        default=None,
        description="Task type label",
    )
    model_override: str | None = Field(
        default=None,
        description="Explicit model reference for manual routing",
    )
    remaining_budget: float | None = Field(
        default=None,
        ge=0.0,
        description="Remaining cost budget in USD",
    )


class RoutingDecision(BaseModel):
    """Output of a routing decision.

    Attributes:
        resolved_model: The chosen model.
        strategy_used: Name of the strategy that produced this decision.
        reason: Human-readable explanation.
        fallbacks_tried: Model refs that were tried before the final choice.
    """

    model_config = ConfigDict(frozen=True)

    resolved_model: ResolvedModel = Field(description="The chosen model")
    strategy_used: str = Field(description="Strategy name")
    reason: str = Field(description="Human-readable explanation")
    fallbacks_tried: tuple[str, ...] = Field(
        default=(),
        description="Model refs tried before the final choice",
    )
