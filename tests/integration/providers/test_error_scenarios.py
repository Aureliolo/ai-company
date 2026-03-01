"""Integration tests: cross-provider error mapping.

Verifies that LiteLLM exceptions raised during ``acompletion`` are
mapped to the correct ``ProviderError`` subclasses with proper
``is_retryable`` flags and metadata.
"""

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from litellm.exceptions import (
    APIConnectionError as LiteLLMConnectionError,
)
from litellm.exceptions import (
    AuthenticationError as LiteLLMAuthError,
)
from litellm.exceptions import (
    InternalServerError as LiteLLMInternalError,
)
from litellm.exceptions import (
    RateLimitError as LiteLLMRateLimit,
)
from litellm.exceptions import (
    Timeout as LiteLLMTimeout,
)

from ai_company.providers import errors
from ai_company.providers.registry import ProviderRegistry

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from ai_company.config.schema import ProviderConfig
    from ai_company.providers.base import BaseCompletionProvider
    from ai_company.providers.models import ChatMessage

from .conftest import (
    build_content_chunk,
    make_anthropic_config,
)

pytestmark = pytest.mark.integration

_PATCH_TARGET = "ai_company.providers.drivers.litellm_driver._litellm.acompletion"


def _make_driver() -> tuple[BaseCompletionProvider, dict[str, ProviderConfig]]:
    """Build an Anthropic driver from config."""
    config = make_anthropic_config()
    registry = ProviderRegistry.from_config(config)
    return registry.get("anthropic"), config


def _make_litellm_rate_limit(
    *,
    retry_after: str | None = None,
) -> LiteLLMRateLimit:
    """Build a LiteLLM RateLimitError with optional retry-after header.

    Sets ``headers`` directly on the exception so the driver's
    ``_extract_retry_after`` can find it (litellm exceptions don't
    expose response headers at the top level).
    """
    response = httpx.Response(
        status_code=429,
        request=httpx.Request("POST", "https://api.anthropic.com/v1/messages"),
    )
    exc = LiteLLMRateLimit(
        message="Rate limit exceeded",
        model="anthropic/claude-sonnet-4-6",
        llm_provider="anthropic",
        response=response,
    )
    if retry_after is not None:
        exc.headers = {"retry-after": retry_after}  # type: ignore[attr-defined]
    return exc


def _make_litellm_auth_error() -> LiteLLMAuthError:
    """Build a LiteLLM AuthenticationError."""
    response = httpx.Response(
        status_code=401,
        request=httpx.Request("POST", "https://api.anthropic.com/v1/messages"),
    )
    return LiteLLMAuthError(
        message="Invalid API key",
        model="anthropic/claude-sonnet-4-6",
        llm_provider="anthropic",
        response=response,
    )


def _make_litellm_timeout() -> LiteLLMTimeout:
    """Build a LiteLLM Timeout error."""
    return LiteLLMTimeout(
        message="Request timed out",
        model="anthropic/claude-sonnet-4-6",
        llm_provider="anthropic",
    )


def _make_litellm_connection_error() -> LiteLLMConnectionError:
    """Build a LiteLLM APIConnectionError."""
    return LiteLLMConnectionError(
        message="Connection refused",
        model="anthropic/claude-sonnet-4-6",
        llm_provider="anthropic",
        request=httpx.Request("POST", "https://api.anthropic.com/v1/messages"),
    )


def _make_litellm_internal_error() -> LiteLLMInternalError:
    """Build a LiteLLM InternalServerError."""
    response = httpx.Response(
        status_code=500,
        request=httpx.Request("POST", "https://api.anthropic.com/v1/messages"),
    )
    return LiteLLMInternalError(
        message="Internal server error",
        model="anthropic/claude-sonnet-4-6",
        llm_provider="anthropic",
        response=response,
    )


# ── Rate limiting ─────────────────────────────────────────────────


async def test_rate_limit_maps_to_retryable_error(
    user_messages: list[ChatMessage],
) -> None:
    """429 -> RateLimitError with is_retryable=True."""
    driver, _ = _make_driver()
    exc = _make_litellm_rate_limit(retry_after="30")

    with (
        patch(_PATCH_TARGET, new_callable=AsyncMock, side_effect=exc),
        pytest.raises(errors.RateLimitError) as exc_info,
    ):
        await driver.complete(user_messages, "sonnet")

    assert exc_info.value.is_retryable is True
    assert exc_info.value.retry_after == 30.0


async def test_rate_limit_without_retry_after(
    user_messages: list[ChatMessage],
) -> None:
    """429 without retry-after header still maps correctly."""
    driver, _ = _make_driver()
    exc = _make_litellm_rate_limit()

    with (
        patch(_PATCH_TARGET, new_callable=AsyncMock, side_effect=exc),
        pytest.raises(errors.RateLimitError) as exc_info,
    ):
        await driver.complete(user_messages, "sonnet")

    assert exc_info.value.is_retryable is True
    assert exc_info.value.retry_after is None


async def test_rate_limit_during_streaming(
    user_messages: list[ChatMessage],
) -> None:
    """Rate limit during streaming raises RateLimitError."""
    driver, _ = _make_driver()
    exc = _make_litellm_rate_limit(retry_after="5")

    async def _failing_stream() -> AsyncIterator[object]:
        yield build_content_chunk("partial")
        raise exc

    mock_stream = _failing_stream()
    with patch(_PATCH_TARGET, new_callable=AsyncMock, return_value=mock_stream):
        stream = await driver.stream(user_messages, "sonnet")
        with pytest.raises(errors.RateLimitError) as exc_info:
            async for _ in stream:
                pass

    assert exc_info.value.is_retryable is True


# ── Authentication ────────────────────────────────────────────────


async def test_auth_error_maps_to_non_retryable(
    user_messages: list[ChatMessage],
) -> None:
    """401 -> AuthenticationError with is_retryable=False."""
    driver, _ = _make_driver()
    exc = _make_litellm_auth_error()

    with (
        patch(_PATCH_TARGET, new_callable=AsyncMock, side_effect=exc),
        pytest.raises(errors.AuthenticationError) as exc_info,
    ):
        await driver.complete(user_messages, "sonnet")

    assert exc_info.value.is_retryable is False
    assert "provider" in exc_info.value.context


# ── Timeout ───────────────────────────────────────────────────────


async def test_timeout_maps_to_retryable(
    user_messages: list[ChatMessage],
) -> None:
    """Timeout -> ProviderTimeoutError with is_retryable=True."""
    driver, _ = _make_driver()
    exc = _make_litellm_timeout()

    with (
        patch(_PATCH_TARGET, new_callable=AsyncMock, side_effect=exc),
        pytest.raises(errors.ProviderTimeoutError) as exc_info,
    ):
        await driver.complete(user_messages, "sonnet")

    assert exc_info.value.is_retryable is True


async def test_timeout_during_streaming(
    user_messages: list[ChatMessage],
) -> None:
    """Timeout during streaming raises ProviderTimeoutError."""
    driver, _ = _make_driver()
    exc = _make_litellm_timeout()

    async def _failing_stream() -> AsyncIterator[object]:
        yield build_content_chunk("partial")
        raise exc

    mock_stream = _failing_stream()
    with patch(_PATCH_TARGET, new_callable=AsyncMock, return_value=mock_stream):
        stream = await driver.stream(user_messages, "sonnet")
        with pytest.raises(errors.ProviderTimeoutError):
            async for _ in stream:
                pass


# ── Connection error ──────────────────────────────────────────────


async def test_connection_error_maps(
    user_messages: list[ChatMessage],
) -> None:
    """Connection error -> ProviderConnectionError."""
    driver, _ = _make_driver()
    exc = _make_litellm_connection_error()

    with (
        patch(_PATCH_TARGET, new_callable=AsyncMock, side_effect=exc),
        pytest.raises(errors.ProviderConnectionError) as exc_info,
    ):
        await driver.complete(user_messages, "sonnet")

    assert exc_info.value.is_retryable is True


# ── Internal server error ─────────────────────────────────────────


async def test_internal_error_maps(
    user_messages: list[ChatMessage],
) -> None:
    """500 -> ProviderInternalError."""
    driver, _ = _make_driver()
    exc = _make_litellm_internal_error()

    with (
        patch(_PATCH_TARGET, new_callable=AsyncMock, side_effect=exc),
        pytest.raises(errors.ProviderInternalError) as exc_info,
    ):
        await driver.complete(user_messages, "sonnet")

    assert exc_info.value.is_retryable is True


# ── Unknown exception fallback ────────────────────────────────────


async def test_unknown_exception_maps_to_internal(
    user_messages: list[ChatMessage],
) -> None:
    """Unexpected exception -> ProviderInternalError fallback."""
    driver, _ = _make_driver()

    with (
        patch(
            _PATCH_TARGET,
            new_callable=AsyncMock,
            side_effect=RuntimeError("something broke"),
        ),
        pytest.raises(errors.ProviderInternalError) as exc_info,
    ):
        await driver.complete(user_messages, "sonnet")

    assert "Unexpected error" in exc_info.value.message
