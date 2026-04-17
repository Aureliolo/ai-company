"""Tests for the Clock protocol and RealClock implementation."""

import asyncio
from datetime import UTC

import pytest

from synthorg.meta.rollout.clock import Clock, RealClock
from tests.unit.meta.rollout._fake_clock import FakeClock

pytestmark = pytest.mark.unit


class TestRealClock:
    """Behavioural tests for the wall-clock implementation.

    Timing is verified by patching ``asyncio.sleep`` and asserting the
    delegated duration, never by measuring wall time. Per CLAUDE.md's
    flaky-test guidance, mocked sleep keeps these tests deterministic
    across machines and CI runners.
    """

    async def test_now_returns_aware_utc(self) -> None:
        clock = RealClock()
        moment = clock.now()
        assert moment.tzinfo is not None
        offset = moment.utcoffset()
        assert offset is not None
        assert offset.total_seconds() == 0.0

    async def test_sleep_delegates_to_asyncio_sleep(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """``RealClock.sleep`` awaits ``asyncio.sleep`` with the same duration."""
        calls: list[float] = []

        async def fake_sleep(seconds: float) -> None:
            calls.append(seconds)

        monkeypatch.setattr(asyncio, "sleep", fake_sleep)
        await RealClock().sleep(0.05)
        assert calls == [0.05]

    async def test_sleep_zero_still_delegates(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """``RealClock.sleep(0.0)`` still hands off to ``asyncio.sleep``."""
        calls: list[float] = []

        async def fake_sleep(seconds: float) -> None:
            calls.append(seconds)

        monkeypatch.setattr(asyncio, "sleep", fake_sleep)
        await RealClock().sleep(0.0)
        assert calls == [0.0]

    async def test_sleep_rejects_negative(self) -> None:
        clock = RealClock()
        with pytest.raises(ValueError, match="non-negative"):
            await clock.sleep(-1.0)

    async def test_is_a_clock(self) -> None:
        assert isinstance(RealClock(), Clock)


class TestFakeClock:
    """Sanity checks for the test helper."""

    async def test_sleep_advances_without_waiting(self) -> None:
        clock = FakeClock()
        started = clock.now()
        await clock.sleep(3600.0)
        elapsed = (clock.now() - started).total_seconds()
        assert elapsed == pytest.approx(3600.0)

    async def test_advance_without_recording(self) -> None:
        clock = FakeClock()
        clock.advance(60.0)
        assert clock.sleep_calls == ()

    async def test_satisfies_clock_protocol(self) -> None:
        clock = FakeClock()
        assert isinstance(clock, Clock)

    async def test_sleep_records_each_call(self) -> None:
        clock = FakeClock()
        await clock.sleep(1.0)
        await clock.sleep(2.5)
        assert clock.sleep_calls == (1.0, 2.5)

    async def test_fake_now_is_aware_utc(self) -> None:
        clock = FakeClock()
        moment = clock.now()
        assert moment.tzinfo is UTC


async def test_asyncio_sleep_is_patchable(monkeypatch: pytest.MonkeyPatch) -> None:
    """``RealClock`` delegates to ``asyncio.sleep`` so tests can patch it."""
    calls: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        calls.append(seconds)

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)
    await RealClock().sleep(7.25)
    assert calls == [7.25]
