"""Model capability descriptors for provider routing decisions."""

from pydantic import BaseModel, ConfigDict, Field

from ai_company.core.types import NotBlankStr  # noqa: TC001


class ModelCapabilities(BaseModel):
    """Static capability and cost metadata for a single LLM model.

    Used by the routing layer to decide which model handles a request
    based on required features (tools, vision, streaming) and cost.

    Attributes:
        model_id: Provider model identifier (e.g. ``"claude-sonnet-4-6"``).
        provider: Provider name (e.g. ``"anthropic"``).
        max_context_tokens: Maximum context window size in tokens.
        max_output_tokens: Maximum output tokens per request.
        supports_tools: Whether the model supports tool/function calling.
        supports_vision: Whether the model accepts image inputs.
        supports_streaming: Whether the model supports streaming responses.
        supports_streaming_tool_calls: Whether tool calls can be streamed.
        supports_system_messages: Whether system messages are accepted.
        cost_per_1k_input: Cost per 1 000 input tokens in USD.
        cost_per_1k_output: Cost per 1 000 output tokens in USD.
    """

    model_config = ConfigDict(frozen=True)

    model_id: NotBlankStr = Field(description="Model identifier")
    provider: NotBlankStr = Field(description="Provider name")
    max_context_tokens: int = Field(gt=0, description="Max context window tokens")
    max_output_tokens: int = Field(gt=0, description="Max output tokens per request")
    supports_tools: bool = Field(default=False, description="Supports tool calling")
    supports_vision: bool = Field(default=False, description="Supports image inputs")
    supports_streaming: bool = Field(
        default=True,
        description="Supports streaming responses",
    )
    supports_streaming_tool_calls: bool = Field(
        default=False,
        description="Supports streaming tool calls",
    )
    supports_system_messages: bool = Field(
        default=True,
        description="Supports system messages",
    )
    cost_per_1k_input: float = Field(
        ge=0.0,
        description="Cost per 1k input tokens in USD",
    )
    cost_per_1k_output: float = Field(
        ge=0.0,
        description="Cost per 1k output tokens in USD",
    )
