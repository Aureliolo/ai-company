"""Deterministic fake Clock implementation for rollout tests.

Satisfies ``synthorg.meta.rollout.clock.Clock`` structurally. Time
advances only when ``advance`` is called explicitly, so observation
windows complete in microseconds regardless of their configured hours.
"""

from datetime import UTC, datetime, timedelta

from pydantic import AwareDatetime


class FakeClock:
    """Virtual clock with manually-advanced time.

    ``sleep`` advances the internal clock without waiting. Tests can
    also advance time directly via ``advance`` (useful when injecting
    side effects between ticks).
    """

    def __init__(self, *, start: AwareDatetime | None = None) -> None:
        self._now: datetime = (
            start
            if start is not None
            else datetime(
                2026,
                1,
                1,
                tzinfo=UTC,
            )
        )
        self._sleep_calls: list[float] = []

    async def sleep(self, seconds: float) -> None:
        """Advance the virtual clock by ``seconds`` without waiting."""
        if seconds < 0.0:
            msg = f"sleep seconds must be non-negative, got {seconds}"
            raise ValueError(msg)
        self._sleep_calls.append(seconds)
        self._now = self._now + timedelta(seconds=seconds)

    def now(self) -> AwareDatetime:
        """Return the current virtual time."""
        return self._now

    def advance(self, seconds: float) -> None:
        """Advance virtual time without recording a sleep call."""
        if seconds < 0.0:
            msg = f"advance seconds must be non-negative, got {seconds}"
            raise ValueError(msg)
        self._now = self._now + timedelta(seconds=seconds)

    @property
    def sleep_calls(self) -> tuple[float, ...]:
        """Seconds passed to every ``sleep`` call, in order."""
        return tuple(self._sleep_calls)
