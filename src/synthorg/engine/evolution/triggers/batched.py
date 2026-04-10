"""Batched (time-interval) evolution trigger.

Fires when enough time has passed since the last evolution run
for an agent. Default interval is one day (86400 seconds).
"""

import asyncio
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from synthorg.observability import get_logger
from synthorg.observability.events.evolution import (
    EVOLUTION_TRIGGER_REQUESTED,
    EVOLUTION_TRIGGER_SKIPPED,
)

if TYPE_CHECKING:
    from synthorg.core.types import NotBlankStr
    from synthorg.engine.evolution.protocols import EvolutionContext

logger = get_logger(__name__)


class BatchedTrigger:
    """Trigger that fires on a time interval.

    Tracks the last evolution time per agent and triggers when
    the configured interval has elapsed.

    Args:
        interval_seconds: Minimum seconds between evolutions.
    """

    def __init__(
        self,
        *,
        interval_seconds: int = 86400,
    ) -> None:
        self._interval = max(1, interval_seconds)
        self._last_run: dict[str, datetime] = {}
        self._lock = asyncio.Lock()

    @property
    def name(self) -> str:
        """Trigger name."""
        return "batched"

    async def should_trigger(
        self,
        *,
        agent_id: NotBlankStr,
        context: EvolutionContext,  # noqa: ARG002
    ) -> bool:
        """Trigger if the interval has elapsed since last run."""
        key = str(agent_id)
        now = datetime.now(UTC)
        async with self._lock:
            last = self._last_run.get(key)

            if last is not None:
                elapsed = (now - last).total_seconds()
                if elapsed < self._interval:
                    logger.debug(
                        EVOLUTION_TRIGGER_SKIPPED,
                        agent_id=key,
                        trigger="batched",
                        reason="interval_not_elapsed",
                        elapsed_seconds=int(elapsed),
                        interval_seconds=self._interval,
                    )
                    return False

            self._last_run[key] = now
            logger.debug(
                EVOLUTION_TRIGGER_REQUESTED,
                agent_id=key,
                trigger="batched",
            )
            return True

    def record_run(self, agent_id: str) -> None:
        """Record that an evolution run completed for an agent."""
        self._last_run[agent_id] = datetime.now(UTC)
