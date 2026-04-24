"""Shared fixtures for engine/quality tests.

Defines the ``ScriptedProvider`` fake used by both LLM decomposer and
LLM grader tests.  Keeping a single shared implementation prevents
silent drift between the two suites.
"""

import copy
from collections.abc import AsyncIterator, Mapping
from typing import Any

from synthorg.providers.capabilities import ModelCapabilities
from synthorg.providers.enums import FinishReason, StreamEventType
from synthorg.providers.models import (
    ChatMessage,
    CompletionConfig,
    CompletionResponse,
    StreamChunk,
    TokenUsage,
    ToolCall,
    ToolDefinition,
)

# Shared capabilities fixture for LLM quality tests.  Kept deliberately
# generic so decomposer and grader suites can both use it without
# reaching for vendor-specific presets.
TEST_CAPABILITIES = ModelCapabilities(
    model_id="test-medium-001",
    provider="test-provider",
    max_context_tokens=200_000,
    max_output_tokens=8_192,
    supports_tools=True,
    supports_vision=False,
    supports_streaming=True,
    supports_streaming_tool_calls=True,
    supports_system_messages=True,
    cost_per_1k_input=0.001,
    cost_per_1k_output=0.002,
)


def build_tool_call_response(  # noqa: PLR0913
    tool_name: str,
    tool_arguments: dict[str, Any],
    *,
    call_id: str = "call-001",
    input_tokens: int = 100,
    output_tokens: int = 30,
    cost: float = 0.0001,
    model: str = "test-medium-001",
) -> CompletionResponse:
    """Build a ``CompletionResponse`` wrapping a single scripted tool call."""
    return CompletionResponse(
        tool_calls=(
            ToolCall(
                id=call_id,
                name=tool_name,
                arguments=tool_arguments,
            ),
        ),
        finish_reason=FinishReason.TOOL_USE,
        usage=TokenUsage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost=cost,
        ),
        model=model,
    )


class ScriptedProvider:
    """Structural ``CompletionProvider`` returning scripted responses.

    Satisfies the ``CompletionProvider`` Protocol (``complete``,
    ``stream``, ``get_model_capabilities``).  ``complete()`` returns the
    configured ``response`` unless ``error`` is set, in which case it
    raises.  All calls are recorded on ``complete_calls`` for assertion.
    """

    def __init__(
        self,
        *,
        response: CompletionResponse | None = None,
        error: Exception | None = None,
        capabilities: ModelCapabilities | None = None,
    ) -> None:
        """Configure the scripted response / error.

        Args:
            response: The response to return from ``complete``.  If
                omitted ``complete`` still records the call but raises
                an ``AssertionError`` -- most tests should supply one.
            error: If set, ``complete`` raises this exception instead
                of returning a response.
            capabilities: Optional override for ``get_model_capabilities``;
                defaults to ``TEST_CAPABILITIES``.
        """
        self._response = response
        self._error = error
        self._capabilities = copy.deepcopy(capabilities or TEST_CAPABILITIES)
        self.complete_calls: list[
            tuple[
                list[ChatMessage],
                str,
                list[ToolDefinition] | None,
                CompletionConfig | None,
            ]
        ] = []

    async def complete(
        self,
        messages: list[ChatMessage],
        model: str,
        *,
        tools: list[ToolDefinition] | None = None,
        config: CompletionConfig | None = None,
    ) -> CompletionResponse:
        """Record the call and return the configured response or raise."""
        # Snapshot mutable inputs so later mutation by callers or retries
        # cannot rewrite recorded history.
        self.complete_calls.append(
            (
                copy.deepcopy(messages),
                model,
                copy.deepcopy(tools),
                copy.deepcopy(config),
            )
        )
        if self._error is not None:
            raise self._error
        if self._response is None:
            msg = (
                "ScriptedProvider.complete() called without a configured "
                "response or error"
            )
            raise AssertionError(msg)
        return self._response

    async def stream(
        self,
        messages: list[ChatMessage],
        model: str,
        *,
        tools: list[ToolDefinition] | None = None,
        config: CompletionConfig | None = None,
    ) -> AsyncIterator[StreamChunk]:
        """Return a trivial single-chunk stream (protocol conformance only).

        The generator yields exactly one ``StreamChunk`` with
        ``event_type=DONE`` so callers can iterate without raising, but
        no content is ever delivered -- tests that care about streaming
        semantics should use a different fake.
        """
        del messages, model, tools, config

        async def _empty() -> AsyncIterator[StreamChunk]:
            yield StreamChunk(event_type=StreamEventType.DONE)

        return _empty()

    async def get_model_capabilities(self, model: str) -> ModelCapabilities:
        """Return the configured capabilities regardless of ``model``."""
        del model
        return self._capabilities

    async def batch_get_capabilities(
        self,
        models: tuple[str, ...],
    ) -> Mapping[str, ModelCapabilities | None]:
        """Return the configured capabilities keyed by each requested model."""
        return dict.fromkeys(models, copy.deepcopy(self._capabilities))
