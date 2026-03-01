"""Abstract base class for completion providers.

Concrete adapters (e.g. ``LiteLLMProvider``) subclass
``BaseCompletionProvider`` and implement the ``_do_*`` hooks.  The base
class handles validation and cost computation.
"""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator  # noqa: TC003

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

    * ``_do_complete`` - raw non-streaming call
    * ``_do_stream`` - raw streaming call
    * ``_do_get_model_capabilities`` - capability lookup

    The public methods add validation and cost computation.
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
            The full completion response.

        Raises:
            InvalidRequestError: If messages are empty.
        """
        self._validate_messages(messages)
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
            Async iterator of stream chunks.

        Raises:
            InvalidRequestError: If messages are empty.
        """
        self._validate_messages(messages)
        return await self._do_stream(
            messages,
            model,
            tools=tools,
            config=config,
        )

    async def get_model_capabilities(self, model: str) -> ModelCapabilities:
        """Delegate to ``_do_get_model_capabilities``.

        Args:
            model: Model identifier.

        Returns:
            Static capability and cost information.
        """
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
        """Provider-specific non-streaming completion."""
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
        """Provider-specific streaming completion."""
        ...

    @abstractmethod
    async def _do_get_model_capabilities(
        self,
        model: str,
    ) -> ModelCapabilities:
        """Provider-specific capability lookup."""
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
            input_tokens: Number of input tokens.
            output_tokens: Number of output tokens.
            cost_per_1k_input: Cost per 1 000 input tokens in USD.
            cost_per_1k_output: Cost per 1 000 output tokens in USD.

        Returns:
            Populated ``TokenUsage`` with computed cost.
        """
        cost = (input_tokens / 1000) * cost_per_1k_input + (
            output_tokens / 1000
        ) * cost_per_1k_output
        return TokenUsage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            cost_usd=round(cost, 10),
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
