"""Abstract base class for completion providers.

Concrete adapters subclass ``BaseCompletionProvider`` and implement
the ``_do_*`` hooks.  The base class handles input validation and
provides a cost-computation helper.
"""

import math
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator  # noqa: TC003

from ai_company.constants import BUDGET_ROUNDING_PRECISION

from .capabilities import ModelCapabilities  # noqa: TC001
from .errors import InvalidRequestError
from .models import (
    ChatMessage,
    CompletionConfig,
    CompletionResponse,
    StreamChunk,
    TokenUsage,
    ToolDefinition,
)


class BaseCompletionProvider(ABC):
    """Shared base for all completion provider adapters.

    Subclasses implement three hooks:

    * ``_do_complete`` — raw non-streaming call
    * ``_do_stream`` — raw streaming call
    * ``_do_get_model_capabilities`` — capability lookup

    The public methods validate inputs before delegating to hooks.
    A static ``compute_cost`` helper is available for subclasses to
    build ``TokenUsage`` records from raw token counts.
    """

    # -- Public API ---------------------------------------------------

    async def complete(
        self,
        messages: list[ChatMessage],
        model: str,
        *,
        tools: list[ToolDefinition] | None = None,
        config: CompletionConfig | None = None,
    ) -> CompletionResponse:
        """Validate inputs, delegate to ``_do_complete``.

        Args:
            messages: Conversation history.
            model: Model identifier to use.
            tools: Available tools for function calling.
            config: Optional completion parameters.

        Returns:
            The completion response returned by the subclass
            ``_do_complete`` hook, unmodified.

        Raises:
            InvalidRequestError: If messages are empty or model is blank.
        """
        self._validate_messages(messages)
        self._validate_model(model)
        return await self._do_complete(
            messages,
            model,
            tools=tools,
            config=config,
        )

    async def stream(
        self,
        messages: list[ChatMessage],
        model: str,
        *,
        tools: list[ToolDefinition] | None = None,
        config: CompletionConfig | None = None,
    ) -> AsyncIterator[StreamChunk]:
        """Validate inputs, delegate to ``_do_stream``.

        Args:
            messages: Conversation history.
            model: Model identifier to use.
            tools: Available tools for function calling.
            config: Optional completion parameters.

        Returns:
            Async iterator of stream chunks returned by the subclass
            ``_do_stream`` hook, unmodified.

        Raises:
            InvalidRequestError: If messages are empty or model is blank.
        """
        self._validate_messages(messages)
        self._validate_model(model)
        return await self._do_stream(
            messages,
            model,
            tools=tools,
            config=config,
        )

    async def get_model_capabilities(self, model: str) -> ModelCapabilities:
        """Validate model identifier, delegate to ``_do_get_model_capabilities``.

        Args:
            model: Model identifier.

        Returns:
            Static capability and cost information.

        Raises:
            InvalidRequestError: If model is blank.
        """
        self._validate_model(model)
        return await self._do_get_model_capabilities(model)

    # -- Hooks (subclasses implement) ---------------------------------

    @abstractmethod
    async def _do_complete(
        self,
        messages: list[ChatMessage],
        model: str,
        *,
        tools: list[ToolDefinition] | None = None,
        config: CompletionConfig | None = None,
    ) -> CompletionResponse:
        """Provider-specific non-streaming completion.

        Subclasses **must** catch all provider-specific exceptions and
        re-raise them as appropriate ``ProviderError`` subclasses.
        Exceptions that escape without wrapping will bypass the error
        hierarchy.

        Raises:
            ProviderError: All errors must use the provider error hierarchy.
        """
        ...

    @abstractmethod
    async def _do_stream(
        self,
        messages: list[ChatMessage],
        model: str,
        *,
        tools: list[ToolDefinition] | None = None,
        config: CompletionConfig | None = None,
    ) -> AsyncIterator[StreamChunk]:
        r"""Provider-specific streaming completion.

        Implementations must *return* an ``AsyncIterator`` (not ``yield``
        directly), since the caller ``await``\s this coroutine to obtain
        the iterator.

        Subclasses **must** catch all provider-specific exceptions and
        re-raise them as appropriate ``ProviderError`` subclasses.

        Raises:
            ProviderError: All errors must use the provider error hierarchy.
        """
        ...

    @abstractmethod
    async def _do_get_model_capabilities(
        self,
        model: str,
    ) -> ModelCapabilities:
        """Provider-specific capability lookup.

        Raises:
            ProviderError: All errors must use the provider error hierarchy.
        """
        ...

    # -- Helpers ------------------------------------------------------

    @staticmethod
    def compute_cost(
        input_tokens: int,
        output_tokens: int,
        *,
        cost_per_1k_input: float,
        cost_per_1k_output: float,
    ) -> TokenUsage:
        """Build a ``TokenUsage`` from raw token counts and per-1k rates.

        Args:
            input_tokens: Number of input tokens (must be >= 0).
            output_tokens: Number of output tokens (must be >= 0).
            cost_per_1k_input: Cost per 1 000 input tokens in USD
                (finite and >= 0).
            cost_per_1k_output: Cost per 1 000 output tokens in USD
                (finite and >= 0).

        Returns:
            Populated ``TokenUsage`` with computed cost.

        Raises:
            InvalidRequestError: If any parameter is negative or
                non-finite.
        """
        if input_tokens < 0:
            msg = "input_tokens must be non-negative"
            raise InvalidRequestError(
                msg,
                context={"input_tokens": input_tokens},
            )
        if output_tokens < 0:
            msg = "output_tokens must be non-negative"
            raise InvalidRequestError(
                msg,
                context={"output_tokens": output_tokens},
            )
        if cost_per_1k_input < 0 or not math.isfinite(cost_per_1k_input):
            msg = "cost_per_1k_input must be a finite non-negative number"
            raise InvalidRequestError(
                msg,
                context={"cost_per_1k_input": cost_per_1k_input},
            )
        if cost_per_1k_output < 0 or not math.isfinite(cost_per_1k_output):
            msg = "cost_per_1k_output must be a finite non-negative number"
            raise InvalidRequestError(
                msg,
                context={"cost_per_1k_output": cost_per_1k_output},
            )
        cost = (input_tokens / 1000) * cost_per_1k_input + (
            output_tokens / 1000
        ) * cost_per_1k_output
        return TokenUsage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            cost_usd=round(cost, BUDGET_ROUNDING_PRECISION),
        )

    @staticmethod
    def _validate_messages(messages: list[ChatMessage]) -> None:
        """Reject empty message lists.

        Args:
            messages: Conversation messages.

        Raises:
            InvalidRequestError: If no messages are provided.
        """
        if not messages:
            msg = "messages must not be empty"
            raise InvalidRequestError(msg, context={"field": "messages"})

    @staticmethod
    def _validate_model(model: str) -> None:
        """Reject blank, empty, or non-string model identifiers.

        Args:
            model: Model identifier string.

        Raises:
            InvalidRequestError: If model is not a string, empty,
                or whitespace-only.
        """
        if not isinstance(model, str) or not model.strip():
            msg = "model must be a non-blank string"
            raise InvalidRequestError(
                msg,
                context={
                    "field": "model",
                    "received_type": type(model).__name__,
                },
            )
