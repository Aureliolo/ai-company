"""Inflection-based evolution trigger.

Subscribes to performance inflection events via the
``InflectionSink`` protocol. When a metric's trend direction
changes, the trigger fires for the affected agent.
"""

import asyncio
from typing import TYPE_CHECKING

from synthorg.observability import get_logger
from synthorg.observability.events.evolution import (
    EVOLUTION_TRIGGER_REQUESTED,
)

if TYPE_CHECKING:
    from synthorg.core.types import NotBlankStr
    from synthorg.engine.evolution.protocols import EvolutionContext
    from synthorg.hr.performance.inflection_protocol import (
        PerformanceInflection,
    )

logger = get_logger(__name__)


class InflectionTrigger:
    """Trigger that fires on performance inflection events.

    Implements both ``EvolutionTrigger`` and ``InflectionSink``
    protocols. The performance tracker emits inflection events to
    this sink, which queues them. ``should_trigger`` checks if
    there are pending inflections for the agent.
    """

    def __init__(self) -> None:
        self._pending: dict[str, list[PerformanceInflection]] = {}
        self._lock = asyncio.Lock()

    @property
    def name(self) -> str:
        return "inflection"

    async def emit(
        self,
        inflection: PerformanceInflection,
    ) -> None:
        """Receive a performance inflection event (InflectionSink)."""
        key = str(inflection.agent_id)
        async with self._lock:
            if key not in self._pending:
                self._pending[key] = []
            self._pending[key].append(inflection)

    async def should_trigger(
        self,
        *,
        agent_id: NotBlankStr,
        context: EvolutionContext,
    ) -> bool:
        """Trigger if there are pending inflections for the agent."""
        key = str(agent_id)
        async with self._lock:
            pending = self._pending.get(key, [])
            if pending:
                self._pending[key] = []
                logger.debug(
                    EVOLUTION_TRIGGER_REQUESTED,
                    agent_id=key,
                    trigger="inflection",
                    inflection_count=len(pending),
                )
                return True
        return False

    async def get_pending(
        self,
        agent_id: str,
    ) -> tuple[PerformanceInflection, ...]:
        """Peek at pending inflections without consuming them."""
        async with self._lock:
            return tuple(self._pending.get(agent_id, []))
