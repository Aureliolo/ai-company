"""Tests for BaseCompletionProvider logging."""

from typing import TYPE_CHECKING

import pytest
import structlog

from synthorg.observability.events.provider import (
    PROVIDER_CALL_ERROR,
    PROVIDER_CALL_START,
    PROVIDER_CALL_SUCCESS,
    PROVIDER_STREAM_START,
)
from synthorg.providers.base import BaseCompletionProvider

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from synthorg.providers.capabilities import ModelCapabilities
    from synthorg.providers.models import (
        ChatMessage,
        CompletionConfig,
        CompletionResponse,
        StreamChunk,
        ToolDefinition,
    )

from synthorg.providers.enums import FinishReason, MessageRole
from synthorg.providers.errors import InvalidRequestError
from synthorg.providers.models import (
    ChatMessage,
    CompletionResponse,
    TokenUsage,
)


class _StubProvider(BaseCompletionProvider):
    """Minimal concrete provider for testing the base class."""

    async def _do_complete(
        self,
        messages: list[ChatMessage],
        model: str,
        *,
        tools: list[ToolDefinition] | None = None,
        config: CompletionConfig | None = None,
    ) -> CompletionResponse:
        return CompletionResponse(
            content="hello",
            tool_calls=(),
            finish_reason=FinishReason.STOP,
            usage=TokenUsage(
                input_tokens=10,
                output_tokens=5,
                cost=0.0,
            ),
            model=model,
        )

    async def _do_stream(
        self,
        messages: list[ChatMessage],
        model: str,
        *,
        tools: list[ToolDefinition] | None = None,
        config: CompletionConfig | None = None,
    ) -> AsyncIterator[StreamChunk]:
        async def _gen() -> AsyncIterator[StreamChunk]:
            return
            yield  # make it an async generator  # type: ignore[unreachable]

        return _gen()

    async def _do_get_model_capabilities(
        self,
        model: str,
    ) -> ModelCapabilities:
        msg = "not implemented"
        raise NotImplementedError(msg)


def _msg(content: str = "hi") -> ChatMessage:
    return ChatMessage(role=MessageRole.USER, content=content)


@pytest.mark.unit
class TestBaseProviderLogging:
    async def test_complete_emits_call_start_and_success(self) -> None:
        provider = _StubProvider()
        with structlog.testing.capture_logs() as cap:
            await provider.complete([_msg()], "test-model")
        start = [e for e in cap if e.get("event") == PROVIDER_CALL_START]
        success = [e for e in cap if e.get("event") == PROVIDER_CALL_SUCCESS]
        assert len(start) == 1
        assert start[0]["model"] == "test-model"
        assert len(success) == 1

    async def test_stream_emits_stream_start(self) -> None:
        provider = _StubProvider()
        with structlog.testing.capture_logs() as cap:
            await provider.stream([_msg()], "test-model")
        events = [e for e in cap if e.get("event") == PROVIDER_STREAM_START]
        assert len(events) == 1
        assert events[0]["model"] == "test-model"

    async def test_empty_messages_emits_error(self) -> None:
        provider = _StubProvider()
        with (
            structlog.testing.capture_logs() as cap,
            pytest.raises(InvalidRequestError),
        ):
            await provider.complete([], "test-model")
        events = [e for e in cap if e.get("event") == PROVIDER_CALL_ERROR]
        assert len(events) == 1

    async def test_blank_model_emits_error(self) -> None:
        provider = _StubProvider()
        with (
            structlog.testing.capture_logs() as cap,
            pytest.raises(InvalidRequestError),
        ):
            await provider.complete([_msg()], "  ")
        events = [e for e in cap if e.get("event") == PROVIDER_CALL_ERROR]
        assert len(events) == 1


@pytest.mark.unit
class TestBaseProviderMetadataEnrichment:
    """BaseCompletionProvider injects _synthorg_* keys into provider_metadata."""

    async def test_latency_ms_injected(self) -> None:
        """_synthorg_latency_ms is a non-negative float."""
        provider = _StubProvider()
        response = await provider.complete([_msg()], "test-model")
        assert "_synthorg_latency_ms" in response.provider_metadata
        assert isinstance(response.provider_metadata["_synthorg_latency_ms"], float)
        assert response.provider_metadata["_synthorg_latency_ms"] >= 0.0

    async def test_no_retry_handler_no_retry_keys(self) -> None:
        """Without a retry handler, retry keys are absent."""
        provider = _StubProvider()
        response = await provider.complete([_msg()], "test-model")
        assert "_synthorg_retry_count" not in response.provider_metadata
        assert "_synthorg_retry_reason" not in response.provider_metadata

    async def test_retry_handler_zero_retries_on_first_success(self) -> None:
        """With a retry handler, _synthorg_retry_count=0 when no retries needed."""
        from synthorg.core.resilience_config import RetryConfig
        from synthorg.providers.resilience.retry import RetryHandler

        config = RetryConfig(
            max_retries=3,
            base_delay=0.001,
            max_delay=0.001,
            exponential_base=2.0,
            jitter=False,
        )
        provider = _StubProvider(retry_handler=RetryHandler(config))
        response = await provider.complete([_msg()], "test-model")
        assert response.provider_metadata["_synthorg_retry_count"] == 0
        assert "_synthorg_retry_reason" not in response.provider_metadata

    async def test_retry_handler_retry_count_reflects_attempts(self) -> None:
        """_synthorg_retry_count equals retry attempts (attempts - 1)."""
        from synthorg.core.resilience_config import RetryConfig
        from synthorg.providers.errors import RateLimitError
        from synthorg.providers.resilience.retry import RetryHandler

        config = RetryConfig(
            max_retries=3,
            base_delay=0.001,
            max_delay=0.001,
            exponential_base=2.0,
            jitter=False,
        )

        calls = 0

        class _RetryableProvider(_StubProvider):
            async def _do_complete(
                self,
                messages: list[ChatMessage],
                model: str,
                *,
                tools: object | None = None,
                config: object | None = None,
            ) -> CompletionResponse:
                nonlocal calls
                calls += 1
                if calls < 3:
                    raise RateLimitError("retry me")  # noqa: TRY003, EM101
                return await super()._do_complete(messages, model)

        provider = _RetryableProvider(retry_handler=RetryHandler(config))
        response = await provider.complete([_msg()], "test-model")
        assert response.provider_metadata["_synthorg_retry_count"] == 2
        assert response.provider_metadata["_synthorg_retry_reason"] == "RateLimitError"
