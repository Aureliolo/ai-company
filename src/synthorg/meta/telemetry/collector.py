"""In-memory analytics collector for cross-deployment events.

Stores anonymized events in memory and delegates pattern
computation to the aggregator module.
"""

import asyncio

from synthorg.meta.telemetry.aggregator import aggregate_patterns
from synthorg.meta.telemetry.models import (  # noqa: TC001
    AggregatedPattern,
    AnonymizedOutcomeEvent,
)
from synthorg.observability import get_logger
from synthorg.observability.events.cross_deployment import (
    XDEPLOY_COLLECTOR_INGESTED,
    XDEPLOY_PATTERN_DETECTED,
)

logger = get_logger(__name__)


class InMemoryAnalyticsCollector:
    """Stores anonymized events in memory and queries patterns.

    Thread-safe via ``asyncio.Lock``. Events are lost on restart;
    suitable for pre-alpha and testing. Production backends can
    implement the ``AnalyticsCollector`` protocol with persistent
    storage.
    """

    def __init__(self) -> None:
        self._events: list[AnonymizedOutcomeEvent] = []
        self._lock = asyncio.Lock()

    @property
    def event_count(self) -> int:
        """Total events stored."""
        return len(self._events)

    async def ingest(
        self,
        events: tuple[AnonymizedOutcomeEvent, ...],
    ) -> int:
        """Ingest a batch of anonymized events.

        Args:
            events: Anonymized events to store.

        Returns:
            Number of events ingested.
        """
        async with self._lock:
            self._events.extend(events)
        logger.info(
            XDEPLOY_COLLECTOR_INGESTED,
            ingested=len(events),
            total=len(self._events),
        )
        return len(events)

    async def query_patterns(
        self,
        *,
        min_deployments: int = 3,
    ) -> tuple[AggregatedPattern, ...]:
        """Query cross-deployment patterns from collected data.

        Args:
            min_deployments: Minimum unique deployments required.

        Returns:
            Aggregated patterns sorted by deployment count.
        """
        async with self._lock:
            snapshot = tuple(self._events)
        patterns = aggregate_patterns(
            snapshot,
            min_deployments=min_deployments,
        )
        if patterns:
            logger.info(
                XDEPLOY_PATTERN_DETECTED,
                pattern_count=len(patterns),
                min_deployments=min_deployments,
            )
        return patterns
