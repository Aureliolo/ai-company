"""Tests for provider-error metric emission in ``BaseCompletionProvider``.

When an underlying driver raises, the base class must classify the
exception (via ``classify_provider_error``) and emit
``synthorg_provider_errors_total`` before re-raising -- so operators
see a per-class error rate even when the caller only catches the
re-raised exception.
"""

from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import MagicMock

import pytest

from synthorg.providers.base import BaseCompletionProvider
from synthorg.providers.enums import FinishReason, MessageRole
from synthorg.providers.errors import (
    ProviderConnectionError,
    RateLimitError,
)
from synthorg.providers.models import (
    ChatMessage,
    CompletionConfig,
    CompletionResponse,
    StreamChunk,
    ToolDefinition,
)

pytestmark = pytest.mark.unit


class _ErroringProvider(BaseCompletionProvider):
    """Provider that raises the configured exception on every call."""

    def __init__(self, *, exc: Exception, provider_name: str = "errp") -> None:
        super().__init__()
        self._provider_name = provider_name
        self._exc = exc

    async def _do_complete(
        self,
        messages: list[ChatMessage],
        model: str,
        *,
        tools: list[ToolDefinition] | None = None,
        config: CompletionConfig | None = None,
    ) -> CompletionResponse:
        raise self._exc

    async def _do_stream(
        self,
        messages: list[ChatMessage],
        model: str,
        *,
        tools: list[ToolDefinition] | None = None,
        config: CompletionConfig | None = None,
    ) -> AsyncIterator[StreamChunk]:
        raise self._exc

    async def _do_get_model_capabilities(
        self,
        model: str,
    ) -> Any:
        raise self._exc


class _SuccessProvider(BaseCompletionProvider):
    """Provider that returns a canned successful response."""

    def __init__(self, *, provider_name: str = "okp") -> None:
        super().__init__()
        self._provider_name = provider_name

    async def _do_complete(
        self,
        messages: list[ChatMessage],
        model: str,
        *,
        tools: list[ToolDefinition] | None = None,
        config: CompletionConfig | None = None,
    ) -> CompletionResponse:
        from synthorg.providers.models import TokenUsage

        return CompletionResponse(
            content="hello",
            tool_calls=(),
            finish_reason=FinishReason.STOP,
            usage=TokenUsage(input_tokens=1, output_tokens=1, cost=0.0),
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
            yield  # type: ignore[unreachable]

        return _gen()

    async def _do_get_model_capabilities(self, model: str) -> Any:
        msg = "not implemented"
        raise NotImplementedError(msg)


async def test_complete_emits_provider_error_with_classification(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``complete`` classifies the raised exception before re-raising."""
    recorder = MagicMock()
    monkeypatch.setattr(
        "synthorg.providers.base.record_provider_error",
        recorder,
    )

    provider = _ErroringProvider(exc=RateLimitError("throttled"))

    with pytest.raises(RateLimitError):
        await provider.complete(
            [ChatMessage(role=MessageRole.USER, content="hi")],
            "example-large-001",
        )

    recorder.assert_called_once_with(
        provider="errp",
        model="example-large-001",
        error_class="rate_limit",
    )


async def test_stream_emits_provider_error_with_classification(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``stream`` classifies the raised exception before re-raising."""
    recorder = MagicMock()
    monkeypatch.setattr(
        "synthorg.providers.base.record_provider_error",
        recorder,
    )

    provider = _ErroringProvider(
        exc=ProviderConnectionError("no route"),
    )

    with pytest.raises(ProviderConnectionError):
        await provider.stream(
            [ChatMessage(role=MessageRole.USER, content="hi")],
            "example-large-001",
        )

    recorder.assert_called_once_with(
        provider="errp",
        model="example-large-001",
        error_class="connection",
    )


async def test_success_does_not_emit_error_metric(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Successful completions never increment the error counter."""
    recorder = MagicMock()
    monkeypatch.setattr(
        "synthorg.providers.base.record_provider_error",
        recorder,
    )

    provider = _SuccessProvider()
    result = await provider.complete(
        [ChatMessage(role=MessageRole.USER, content="hi")],
        "example-large-001",
    )
    assert result.content == "hello"
    recorder.assert_not_called()


def test_provider_label_defaults_to_class_name() -> None:
    """Subclasses without ``provider_name`` fall back to the class name."""

    class _Unbranded(BaseCompletionProvider):
        async def _do_complete(self, *a: Any, **kw: Any) -> Any: ...  # type: ignore[override]

        async def _do_stream(self, *a: Any, **kw: Any) -> Any: ...  # type: ignore[override]

        async def _do_get_model_capabilities(self, model: str) -> Any: ...  # type: ignore[override]

    p = _Unbranded()
    assert p._provider_label() == "_Unbranded"
