"""Unit tests for the in-memory inflight store (#1489, SEC-2)."""

import asyncio

import pytest

from synthorg.api.errors import ConcurrencyLimitExceededError
from synthorg.api.rate_limits.in_memory_inflight import InMemoryInflightStore

pytestmark = pytest.mark.unit


class TestAcquireRelease:
    """Basic acquire/release: counter increments and decrements."""

    async def test_acquire_below_cap_succeeds(self) -> None:
        store = InMemoryInflightStore()
        try:
            async with store.acquire("op:user-1", max_inflight=2):
                assert store._counters["op:user-1"] == 1
            assert store._counters["op:user-1"] == 0
        finally:
            await store.close()

    async def test_sequential_acquires_at_cap_succeed(self) -> None:
        store = InMemoryInflightStore()
        try:
            for _ in range(5):
                async with store.acquire("op:user-1", max_inflight=1):
                    assert store._counters["op:user-1"] == 1
                assert store._counters["op:user-1"] == 0
        finally:
            await store.close()

    async def test_release_on_exception_decrements(self) -> None:
        store = InMemoryInflightStore()

        async def raise_inside_permit() -> None:
            async with store.acquire("op:user-1", max_inflight=1):
                assert store._counters["op:user-1"] == 1
                msg = "boom"
                raise RuntimeError(msg)

        try:
            with pytest.raises(RuntimeError, match="boom"):
                await raise_inside_permit()
            assert store._counters["op:user-1"] == 0
        finally:
            await store.close()


class TestConcurrencyDenial:
    """Over-limit requests raise ConcurrencyLimitExceededError."""

    async def test_concurrent_at_cap_raises(self) -> None:
        store = InMemoryInflightStore()
        gate = asyncio.Event()

        async def holder() -> None:
            async with store.acquire("op:user-1", max_inflight=1):
                await gate.wait()

        async def attempt() -> ConcurrencyLimitExceededError:
            try:
                async with store.acquire("op:user-1", max_inflight=1):
                    msg = "Second acquire should have been denied"
                    raise AssertionError(msg)
            except ConcurrencyLimitExceededError as exc:
                return exc

        try:
            holder_task = asyncio.create_task(holder())
            # Yield so the holder takes the permit before the attempt.
            await asyncio.sleep(0)
            err = await attempt()
            assert err.retry_after == 1
            assert err.status_code == 429
            assert err.error_code.value == 5002
            gate.set()
            await holder_task
        finally:
            await store.close()

    async def test_release_reopens_slot(self) -> None:
        store = InMemoryInflightStore()
        try:
            async with store.acquire("op:user-1", max_inflight=1):
                pass
            async with store.acquire("op:user-1", max_inflight=1):
                assert store._counters["op:user-1"] == 1
        finally:
            await store.close()

    async def test_distinct_keys_dont_share_cap(self) -> None:
        store = InMemoryInflightStore()
        try:
            async with (
                store.acquire("op:user-1", max_inflight=1),
                store.acquire("op:user-2", max_inflight=1),
            ):
                assert store._counters["op:user-1"] == 1
                assert store._counters["op:user-2"] == 1
        finally:
            await store.close()


class TestValidation:
    """Invalid max_inflight raises ValueError immediately."""

    async def test_zero_max_inflight_raises(self) -> None:
        store = InMemoryInflightStore()
        try:
            with pytest.raises(ValueError, match="max_inflight"):
                store.acquire("op:user-1", max_inflight=0)
        finally:
            await store.close()

    async def test_negative_max_inflight_raises(self) -> None:
        store = InMemoryInflightStore()
        try:
            with pytest.raises(ValueError, match="max_inflight"):
                store.acquire("op:user-1", max_inflight=-5)
        finally:
            await store.close()


class TestClose:
    """close() clears internal state."""

    async def test_close_clears_counters(self) -> None:
        store = InMemoryInflightStore()
        async with store.acquire("op:user-1", max_inflight=1):
            pass
        assert "op:user-1" in store._counters
        await store.close()
        assert not store._counters
        assert not store._locks
