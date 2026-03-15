"""Tests for RateLimiter."""

import asyncio
import contextlib
from unittest import mock

import pytest
import structlog

from synthorg.core.resilience_config import RateLimiterConfig
from synthorg.observability.events.provider import (
    PROVIDER_RATE_LIMITER_PAUSED,
    PROVIDER_RATE_LIMITER_THROTTLED,
)
from synthorg.providers.resilience.rate_limiter import RateLimiter

pytestmark = [pytest.mark.timeout(30), pytest.mark.unit]


class TestRateLimiterDisabled:
    async def test_disabled_by_default(self) -> None:
        limiter = RateLimiter(
            RateLimiterConfig(),
            provider_name="test-provider",
        )
        assert limiter.is_enabled is False

    async def test_acquire_release_noop_when_disabled(self) -> None:
        limiter = RateLimiter(
            RateLimiterConfig(),
            provider_name="test-provider",
        )
        await limiter.acquire()
        limiter.release()  # should not raise


class TestRateLimiterConcurrency:
    async def test_concurrent_limit(self) -> None:
        config = RateLimiterConfig(max_concurrent=2)
        limiter = RateLimiter(config, provider_name="test-provider")
        assert limiter.is_enabled is True

        # Acquire 2 slots
        await limiter.acquire()
        await limiter.acquire()

        # Third acquire should block; verify with a short timeout
        acquired = asyncio.Event()

        async def _try_acquire() -> None:
            await limiter.acquire()
            acquired.set()

        task = asyncio.create_task(_try_acquire())
        try:
            # Yield control so _try_acquire starts and blocks on semaphore
            await asyncio.sleep(0)
            await asyncio.sleep(0)
            assert not acquired.is_set()

            # Release one slot and yield so the blocked task can proceed
            limiter.release()
            await asyncio.sleep(0)
            await asyncio.sleep(0)
            assert acquired.is_set()

            # Release the remaining two slots
            limiter.release()
            limiter.release()
        finally:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    async def test_release_without_acquire_does_not_crash(self) -> None:
        config = RateLimiterConfig(max_concurrent=2)
        limiter = RateLimiter(config, provider_name="test-provider")
        # Extra release (semaphore goes above initial count, but doesn't crash)
        limiter.release()


class TestRateLimiterRPM:
    async def test_rpm_enabled(self) -> None:
        config = RateLimiterConfig(max_requests_per_minute=60)
        limiter = RateLimiter(config, provider_name="test-provider")
        assert limiter.is_enabled is True

    async def test_rpm_allows_within_limit(self) -> None:
        config = RateLimiterConfig(max_requests_per_minute=100)
        limiter = RateLimiter(config, provider_name="test-provider")

        # Should be able to acquire many times quickly
        for _ in range(10):
            await limiter.acquire()


class TestRateLimiterPause:
    async def test_pause_blocks_acquire(self) -> None:
        """acquire() sleeps for the remaining pause duration."""
        config = RateLimiterConfig(max_concurrent=10)
        limiter = RateLimiter(config, provider_name="test-provider")

        base_t = 500_000.0
        call_count = 0

        def time_fn() -> float:
            nonlocal call_count
            call_count += 1
            # pause() sees base_t; acquire() loop sees base_t + 0.02
            # (still within pause window); after sleep sees base_t + 0.2
            if call_count <= 2:
                return base_t
            if call_count == 3:
                return base_t + 0.02
            return base_t + 0.2

        slept_for: float | None = None

        async def fake_sleep(seconds: float) -> None:
            nonlocal slept_for
            slept_for = seconds

        with (
            mock.patch(
                "synthorg.providers.resilience.rate_limiter.time.monotonic",
                time_fn,
            ),
            mock.patch(
                "synthorg.providers.resilience.rate_limiter.asyncio.sleep",
                fake_sleep,
            ),
        ):
            limiter.pause(0.1)
            await limiter.acquire()

        assert slept_for is not None
        assert slept_for > 0  # must have waited
        limiter.release()

    async def test_pause_extends_if_longer(self) -> None:
        """A longer second pause extends the pause window."""
        config = RateLimiterConfig(max_concurrent=10)
        limiter = RateLimiter(config, provider_name="test-provider")

        base_t = 600_000.0
        call_count = 0

        def time_fn() -> float:
            nonlocal call_count
            call_count += 1
            if call_count <= 3:
                return base_t
            if call_count == 4:
                return base_t + 0.01  # still in pause window
            return base_t + 0.2  # after sleep, past pause

        slept_for: float | None = None

        async def fake_sleep(seconds: float) -> None:
            nonlocal slept_for
            slept_for = seconds

        with (
            mock.patch(
                "synthorg.providers.resilience.rate_limiter.time.monotonic",
                time_fn,
            ),
            mock.patch(
                "synthorg.providers.resilience.rate_limiter.asyncio.sleep",
                fake_sleep,
            ),
        ):
            limiter.pause(0.05)
            limiter.pause(0.15)  # extends
            await limiter.acquire()

        # Should have waited for the longer pause
        assert slept_for is not None
        assert slept_for > 0.10
        limiter.release()

    async def test_pause_no_extend_if_shorter(self) -> None:
        """A shorter second pause does not reduce the pause window."""
        config = RateLimiterConfig(max_concurrent=10)
        limiter = RateLimiter(config, provider_name="test-provider")

        base_t = 700_000.0
        call_count = 0

        def time_fn() -> float:
            nonlocal call_count
            call_count += 1
            if call_count <= 3:
                return base_t
            if call_count == 4:
                return base_t + 0.01
            return base_t + 0.2

        slept_for: float | None = None

        async def fake_sleep(seconds: float) -> None:
            nonlocal slept_for
            slept_for = seconds

        with (
            mock.patch(
                "synthorg.providers.resilience.rate_limiter.time.monotonic",
                time_fn,
            ),
            mock.patch(
                "synthorg.providers.resilience.rate_limiter.asyncio.sleep",
                fake_sleep,
            ),
        ):
            limiter.pause(0.15)
            limiter.pause(0.01)  # shorter, should not reduce
            await limiter.acquire()

        # Should have waited ~0.14s (the original longer pause minus elapsed)
        assert slept_for is not None
        assert slept_for > 0.10
        limiter.release()

    async def test_pause_rejects_negative(self) -> None:
        limiter = RateLimiter(RateLimiterConfig(), provider_name="test-provider")
        with pytest.raises(ValueError, match="finite non-negative"):
            limiter.pause(-1.0)

    async def test_pause_rejects_inf(self) -> None:
        limiter = RateLimiter(RateLimiterConfig(), provider_name="test-provider")
        with pytest.raises(ValueError, match="finite non-negative"):
            limiter.pause(float("inf"))

    async def test_pause_rejects_nan(self) -> None:
        limiter = RateLimiter(RateLimiterConfig(), provider_name="test-provider")
        with pytest.raises(ValueError, match="finite non-negative"):
            limiter.pause(float("nan"))


class TestRateLimiterRPMThrottling:
    async def test_rpm_throttles_when_over_limit(self) -> None:
        """acquire() sleeps when RPM budget is exhausted, then retries."""
        config = RateLimiterConfig(max_requests_per_minute=1)
        limiter = RateLimiter(config, provider_name="test-provider")

        base_t = 1_000_000.0
        slept = False

        async def instant_sleep(seconds: float) -> None:
            nonlocal slept
            slept = True

        def time_fn() -> float:
            return base_t if not slept else base_t + 61.0

        # Fill the single RPM slot
        with mock.patch(
            "synthorg.providers.resilience.rate_limiter.time.monotonic",
            time_fn,
        ):
            await limiter.acquire()

        # Second acquire must sleep (budget exhausted)
        with (
            mock.patch(
                "synthorg.providers.resilience.rate_limiter.time.monotonic",
                time_fn,
            ),
            mock.patch(
                "synthorg.providers.resilience.rate_limiter.asyncio.sleep",
                instant_sleep,
            ),
        ):
            await limiter.acquire()

        assert slept

    async def test_rpm_throttle_logs_rpm_limit_reason(self) -> None:
        """RPM throttling emits a log entry with reason='rpm_limit'."""
        config = RateLimiterConfig(max_requests_per_minute=1)
        limiter = RateLimiter(config, provider_name="test-provider")

        base_t = 2_000_000.0
        slept = False

        async def instant_sleep(seconds: float) -> None:
            nonlocal slept
            slept = True

        def time_fn() -> float:
            return base_t if not slept else base_t + 61.0

        with mock.patch(
            "synthorg.providers.resilience.rate_limiter.time.monotonic",
            time_fn,
        ):
            await limiter.acquire()

        with (
            mock.patch(
                "synthorg.providers.resilience.rate_limiter.time.monotonic",
                time_fn,
            ),
            mock.patch(
                "synthorg.providers.resilience.rate_limiter.asyncio.sleep",
                instant_sleep,
            ),
            structlog.testing.capture_logs() as cap,
        ):
            await limiter.acquire()

        rpm_logs = [e for e in cap if e.get("reason") == "rpm_limit"]
        assert len(rpm_logs) >= 1


class TestRateLimiterLogging:
    async def test_logs_pause(self) -> None:
        config = RateLimiterConfig(max_concurrent=10)
        limiter = RateLimiter(config, provider_name="test-provider")

        with structlog.testing.capture_logs() as cap:
            limiter.pause(1.0)

        paused = [e for e in cap if e.get("event") == PROVIDER_RATE_LIMITER_PAUSED]
        assert len(paused) == 1
        assert paused[0]["provider"] == "test-provider"

    async def test_logs_throttle_on_pause_active(self) -> None:
        config = RateLimiterConfig(max_concurrent=10)
        limiter = RateLimiter(config, provider_name="test-provider")

        limiter.pause(0.05)
        with structlog.testing.capture_logs() as cap:
            await limiter.acquire()

        throttled = [
            e for e in cap if e.get("event") == PROVIDER_RATE_LIMITER_THROTTLED
        ]
        assert len(throttled) >= 1
        assert throttled[0]["reason"] == "pause_active"

        limiter.release()
