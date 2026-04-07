"""Tests for RetryHandler metadata state (last_attempt_count, last_retry_reason)."""

import pytest

from synthorg.core.resilience_config import RetryConfig
from synthorg.providers.errors import (
    ProviderConnectionError,
    RateLimitError,
)
from synthorg.providers.resilience.errors import RetryExhaustedError
from synthorg.providers.resilience.retry import RetryHandler


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
    """last_attempt_count and last_retry_reason are exposed after execute()."""

    def test_initial_state(self) -> None:
        """Before any call, counters are at their zero values."""
        handler = RetryHandler(_config())
        assert handler.last_attempt_count == 0
        assert handler.last_retry_reason is None

    async def test_success_on_first_try(self) -> None:
        """One attempt, no retries -- count=1, reason=None."""
        handler = RetryHandler(_config())

        async def _func() -> str:
            return "ok"

        await handler.execute(_func)
        assert handler.last_attempt_count == 1
        assert handler.last_retry_reason is None

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

        await handler.execute(_func)
        assert handler.last_attempt_count == 3
        assert handler.last_retry_reason == "RateLimitError"

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

        await handler.execute(_func)
        assert handler.last_retry_reason == "ProviderConnectionError"

    async def test_state_reset_between_executions(self) -> None:
        """State is reset at the start of each execute() call."""
        handler = RetryHandler(_config(max_retries=3))
        calls = 0

        async def _fail_once() -> str:
            nonlocal calls
            calls += 1
            if calls == 1:
                raise RateLimitError("retry me")  # noqa: TRY003, EM101
            return "ok"

        await handler.execute(_fail_once)
        assert handler.last_attempt_count == 2
        assert handler.last_retry_reason == "RateLimitError"

        calls = 0

        async def _succeed() -> str:
            return "ok"

        await handler.execute(_succeed)
        assert handler.last_attempt_count == 1
        assert handler.last_retry_reason is None

    async def test_exhausted_retries_still_updates_count(self) -> None:
        """Even when all retries fail, count reflects total attempts."""
        handler = RetryHandler(_config(max_retries=2))

        async def _always_fail() -> str:
            raise RateLimitError("always fails")  # noqa: TRY003, EM101

        with pytest.raises(RetryExhaustedError):
            await handler.execute(_always_fail)

        assert handler.last_attempt_count == 3  # initial + 2 retries
        assert handler.last_retry_reason == "RateLimitError"

    async def test_non_retryable_error_count_one(self) -> None:
        """Non-retryable errors raise immediately with count=1."""
        from synthorg.providers.errors import InvalidRequestError

        handler = RetryHandler(_config(max_retries=3))

        async def _bad_request() -> str:
            raise InvalidRequestError("bad")  # noqa: EM101

        with pytest.raises(InvalidRequestError):
            await handler.execute(_bad_request)

        assert handler.last_attempt_count == 1
