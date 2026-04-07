"""Tests for RetryHandler and RetryResult metadata."""

import pytest

from synthorg.core.resilience_config import RetryConfig
from synthorg.providers.errors import (
    ProviderConnectionError,
    RateLimitError,
)
from synthorg.providers.resilience.errors import RetryExhaustedError
from synthorg.providers.resilience.retry import RetryHandler, RetryResult


def _config(*, max_retries: int = 3, jitter: bool = False) -> RetryConfig:
    return RetryConfig(
        max_retries=max_retries,
        base_delay=0.001,
        max_delay=0.001,
        exponential_base=2.0,
        jitter=jitter,
    )


@pytest.mark.unit
class TestRetryHandlerMetadataState:
    """RetryResult carries per-invocation retry metadata."""

    async def test_success_on_first_try(self) -> None:
        """One attempt, no retries -- count=1, reason=None."""
        handler = RetryHandler(_config())

        async def _func() -> str:
            return "ok"

        result = await handler.execute(_func)
        assert isinstance(result, RetryResult)
        assert result.value == "ok"
        assert result.attempt_count == 1
        assert result.retry_reason is None

    async def test_success_after_retries(self) -> None:
        """Two transient failures then success -- count=3, reason set."""
        handler = RetryHandler(_config(max_retries=3))
        calls = 0

        async def _func() -> str:
            nonlocal calls
            calls += 1
            if calls < 3:
                raise RateLimitError("rate limited")  # noqa: TRY003, EM101
            return "ok"

        result = await handler.execute(_func)
        assert result.attempt_count == 3
        assert result.retry_reason == "RateLimitError"

    async def test_reason_reflects_last_retried_error_type(self) -> None:
        """retry_reason uses the exception class name."""
        handler = RetryHandler(_config(max_retries=3))
        calls = 0

        async def _func() -> str:
            nonlocal calls
            calls += 1
            if calls == 1:
                raise ProviderConnectionError("connection failed")  # noqa: TRY003, EM101
            return "ok"

        result = await handler.execute(_func)
        assert result.retry_reason == "ProviderConnectionError"

    async def test_state_independent_between_executions(self) -> None:
        """Each execute() returns its own independent RetryResult."""
        handler = RetryHandler(_config(max_retries=3))
        calls = 0

        async def _fail_once() -> str:
            nonlocal calls
            calls += 1
            if calls == 1:
                raise RateLimitError("retry me")  # noqa: TRY003, EM101
            return "ok"

        result1 = await handler.execute(_fail_once)
        assert result1.attempt_count == 2
        assert result1.retry_reason == "RateLimitError"

        async def _succeed() -> str:
            return "ok"

        result2 = await handler.execute(_succeed)
        assert result2.attempt_count == 1
        assert result2.retry_reason is None
        # result1 is immutable -- verify it wasn't affected
        assert result1.attempt_count == 2
        assert result1.retry_reason == "RateLimitError"

    async def test_exhausted_retries_raises(self) -> None:
        """When all retries fail, RetryExhaustedError is raised."""
        handler = RetryHandler(_config(max_retries=2))

        async def _always_fail() -> str:
            raise RateLimitError("always fails")  # noqa: TRY003, EM101

        with pytest.raises(RetryExhaustedError):
            await handler.execute(_always_fail)

    async def test_non_retryable_error_raises_immediately(self) -> None:
        """Non-retryable errors raise immediately without retry."""
        from synthorg.providers.errors import InvalidRequestError

        handler = RetryHandler(_config(max_retries=3))

        async def _bad_request() -> str:
            raise InvalidRequestError("bad")  # noqa: EM101

        with pytest.raises(InvalidRequestError):
            await handler.execute(_bad_request)
