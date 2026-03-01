"""Provider-layer domain models for chat completion requests and responses."""

from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ai_company.core.types import NotBlankStr  # noqa: TC001

from .enums import FinishReason, MessageRole, StreamEventType


class TokenUsage(BaseModel):
    """Token counts and cost for a single completion call.

    This is the lightweight provider-layer record.  The budget layer's
    ``CostRecord`` adds agent/task context around it.

    Attributes:
        input_tokens: Number of input (prompt) tokens.
        output_tokens: Number of output (completion) tokens.
        total_tokens: Sum of input and output tokens.
        cost_usd: Estimated cost in USD for this call.
    """

    model_config = ConfigDict(frozen=True)

    input_tokens: int = Field(ge=0, description="Input token count")
    output_tokens: int = Field(ge=0, description="Output token count")
    total_tokens: int = Field(ge=0, description="Total token count")
    cost_usd: float = Field(ge=0.0, description="Estimated cost in USD")

    @model_validator(mode="after")
    def _validate_total(self) -> Self:
        """Ensure total_tokens equals the sum of input and output tokens."""
        expected = self.input_tokens + self.output_tokens
        if self.total_tokens != expected:
            msg = (
                f"total_tokens ({self.total_tokens}) must equal "
                f"input_tokens + output_tokens ({expected})"
            )
            raise ValueError(msg)
        return self


class ToolDefinition(BaseModel):
    """Schema for a tool the model can invoke.

    Uses raw JSON Schema for ``parameters_schema`` because every LLM
    provider (OpenAI, Anthropic, LiteLLM) consumes it natively.

    Attributes:
        name: Tool name (must be non-blank).
        description: Human-readable description of the tool.
        parameters_schema: JSON Schema dict describing the tool parameters.
    """

    model_config = ConfigDict(frozen=True)

    name: NotBlankStr = Field(description="Tool name")
    description: str = Field(default="", description="Tool description")
    parameters_schema: dict[str, Any] = Field(
        default_factory=dict,
        description="JSON Schema for tool parameters",
    )


class ToolCall(BaseModel):
    """A tool invocation requested by the model.

    Attributes:
        id: Provider-assigned tool call identifier.
        name: Name of the tool to invoke.
        arguments: Parsed arguments dict.
    """

    model_config = ConfigDict(frozen=True)

    id: NotBlankStr = Field(description="Tool call identifier")
    name: NotBlankStr = Field(description="Tool name")
    arguments: dict[str, Any] = Field(
        default_factory=dict,
        description="Tool arguments",
    )


class ToolResult(BaseModel):
    """Result of executing a tool call, sent back to the model.

    Attributes:
        tool_call_id: The ``ToolCall.id`` this result corresponds to.
        content: String content returned by the tool.
        is_error: Whether the tool execution failed.
    """

    model_config = ConfigDict(frozen=True)

    tool_call_id: NotBlankStr = Field(description="Matching tool call ID")
    content: str = Field(description="Tool output content")
    is_error: bool = Field(default=False, description="Whether tool errored")


class ChatMessage(BaseModel):
    """A single message in a chat completion conversation.

    Attributes:
        role: Message role (system, user, assistant, tool).
        content: Text content of the message.
        tool_calls: Tool calls requested by the assistant (assistant only).
        tool_result: Result of a tool execution (tool role only).
    """

    model_config = ConfigDict(frozen=True)

    role: MessageRole = Field(description="Message role")
    content: str | None = Field(default=None, description="Text content")
    tool_calls: tuple[ToolCall, ...] = Field(
        default=(),
        description="Tool calls (assistant messages only)",
    )
    tool_result: ToolResult | None = Field(
        default=None,
        description="Tool result (tool messages only)",
    )

    @model_validator(mode="after")
    def _validate_role_constraints(self) -> Self:
        """Enforce role-specific field constraints."""
        if self.role == MessageRole.TOOL:
            if self.tool_result is None:
                msg = "tool messages must include a tool_result"
                raise ValueError(msg)
            if self.tool_calls:
                msg = "tool messages must not include tool_calls"
                raise ValueError(msg)

        if self.role == MessageRole.ASSISTANT and self.tool_result is not None:
            msg = "assistant messages must not include a tool_result"
            raise ValueError(msg)

        if self.role in (MessageRole.SYSTEM, MessageRole.USER):
            if self.tool_calls:
                msg = f"{self.role} messages must not include tool_calls"
                raise ValueError(msg)
            if self.tool_result is not None:
                msg = f"{self.role} messages must not include a tool_result"
                raise ValueError(msg)

        if (
            self.role != MessageRole.TOOL
            and self.content is None
            and not self.tool_calls
        ):
            msg = f"{self.role} messages must have content or tool_calls"
            raise ValueError(msg)

        return self


class CompletionConfig(BaseModel):
    """Optional parameters for a completion request.

    All fields are optional — the provider fills in defaults.

    Attributes:
        temperature: Sampling temperature (0.0-2.0).
        max_tokens: Maximum tokens to generate.
        stop_sequences: Sequences that stop generation.
        top_p: Nucleus sampling threshold.
        timeout: Request timeout in seconds.
    """

    model_config = ConfigDict(frozen=True)

    temperature: float | None = Field(
        default=None,
        ge=0.0,
        le=2.0,
        description="Sampling temperature",
    )
    max_tokens: int | None = Field(
        default=None,
        gt=0,
        description="Maximum tokens to generate",
    )
    stop_sequences: tuple[str, ...] = Field(
        default=(),
        description="Stop sequences",
    )
    top_p: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Nucleus sampling threshold",
    )
    timeout: float | None = Field(
        default=None,
        gt=0.0,
        description="Request timeout in seconds",
    )


class CompletionResponse(BaseModel):
    """Result of a non-streaming completion call.

    Attributes:
        content: Generated text content (may be ``None`` for tool-use-only responses).
        tool_calls: Tool calls the model wants to execute.
        finish_reason: Why the model stopped generating.
        usage: Token usage and cost breakdown.
        model: Model identifier that served the request.
        provider_request_id: Provider-assigned request ID for debugging.
    """

    model_config = ConfigDict(frozen=True)

    content: str | None = Field(default=None, description="Generated text")
    tool_calls: tuple[ToolCall, ...] = Field(
        default=(),
        description="Requested tool calls",
    )
    finish_reason: FinishReason = Field(description="Reason generation stopped")
    usage: TokenUsage = Field(description="Token usage breakdown")
    model: NotBlankStr = Field(description="Model that served the request")
    provider_request_id: str | None = Field(
        default=None,
        description="Provider request ID",
    )


class StreamChunk(BaseModel):
    """A single chunk from a streaming completion response.

    The ``event_type`` discriminator determines which optional fields are
    populated.

    Attributes:
        event_type: Type of stream event.
        content: Text delta (for ``content_delta``).
        tool_call_delta: Partial tool call (for ``tool_call_delta``).
        usage: Final token usage (for ``usage`` event).
        error_message: Error description (for ``error`` event).
    """

    model_config = ConfigDict(frozen=True)

    event_type: StreamEventType = Field(description="Stream event type")
    content: str | None = Field(default=None, description="Text delta")
    tool_call_delta: ToolCall | None = Field(
        default=None,
        description="Partial tool call",
    )
    usage: TokenUsage | None = Field(
        default=None,
        description="Final token usage",
    )
    error_message: str | None = Field(
        default=None,
        description="Error description",
    )

    @model_validator(mode="after")
    def _validate_event_fields(self) -> Self:
        """Ensure the populated fields match the event_type."""
        match self.event_type:
            case StreamEventType.CONTENT_DELTA:
                if self.content is None:
                    msg = "content_delta event must include content"
                    raise ValueError(msg)
            case StreamEventType.TOOL_CALL_DELTA:
                if self.tool_call_delta is None:
                    msg = "tool_call_delta event must include tool_call_delta"
                    raise ValueError(msg)
            case StreamEventType.USAGE:
                if self.usage is None:
                    msg = "usage event must include usage"
                    raise ValueError(msg)
            case StreamEventType.ERROR:
                if self.error_message is None:
                    msg = "error event must include error_message"
                    raise ValueError(msg)
        return self
