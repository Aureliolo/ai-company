"""Clock abstraction for the rollout subsystem.

The observation loop needs to sleep for configurable hours and
timestamp samples. Wrapping those two operations behind a protocol
lets tests substitute a deterministic fake clock for wall time.
"""

import asyncio
from datetime import UTC, datetime
from typing import Protocol, runtime_checkable

from pydantic import AwareDatetime  # noqa: TC002 -- used in protocol return type


@runtime_checkable
class Clock(Protocol):
    """Abstract source of time for rollout strategies.

    Implementations provide asynchronous sleeping and UTC-aware
    wall-time readings. The real implementation defers to ``asyncio``.
    """

    async def sleep(self, seconds: float) -> None:
        """Suspend the caller for approximately ``seconds``.

        Args:
            seconds: Non-negative duration.
        """
        ...

    def now(self) -> AwareDatetime:
        """Return the current UTC-aware wall-clock time."""
        ...


class RealClock:
    """Wall-clock implementation backed by ``asyncio`` and ``datetime``."""

    async def sleep(self, seconds: float) -> None:
        """Await ``asyncio.sleep`` for the requested duration."""
        if seconds < 0.0:
            msg = f"sleep seconds must be non-negative, got {seconds}"
            raise ValueError(msg)
        await asyncio.sleep(seconds)

    def now(self) -> AwareDatetime:
        """Return the current time as a UTC-aware datetime."""
        return datetime.now(UTC)
