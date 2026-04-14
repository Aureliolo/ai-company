"""Telemetry signal aggregator.

Wraps the telemetry pipeline to produce an OrgTelemetrySummary
with event counts and top event types.
"""

from typing import TYPE_CHECKING

from synthorg.core.types import NotBlankStr
from synthorg.meta.models import OrgTelemetrySummary
from synthorg.observability import get_logger
from synthorg.observability.events.meta import META_SIGNAL_AGGREGATION_COMPLETED

if TYPE_CHECKING:
    from datetime import datetime

logger = get_logger(__name__)

_EMPTY = OrgTelemetrySummary()


class TelemetrySignalAggregator:
    """Aggregates telemetry events into org-wide summaries."""

    @property
    def domain(self) -> NotBlankStr:
        """Signal domain name."""
        return NotBlankStr("telemetry")

    async def aggregate(
        self,
        *,
        since: datetime,
        until: datetime,
    ) -> OrgTelemetrySummary:
        """Aggregate telemetry signals for the time window.

        Args:
            since: Start of observation window.
            until: End of observation window.

        Returns:
            Org-wide telemetry summary.
        """
        _ = since, until  # Will be used by real implementation.
        logger.info(
            META_SIGNAL_AGGREGATION_COMPLETED,
            domain="telemetry",
        )
        return _EMPTY
