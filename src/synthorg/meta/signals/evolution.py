"""Evolution outcomes signal aggregator.

Wraps the EvolutionService to produce an OrgEvolutionSummary
with recent proposals, approval rates, and axis distributions.
"""

from typing import TYPE_CHECKING

from synthorg.core.types import NotBlankStr
from synthorg.meta.models import OrgEvolutionSummary
from synthorg.observability import get_logger
from synthorg.observability.events.meta import (
    META_SIGNAL_AGGREGATION_COMPLETED,
    META_SIGNAL_AGGREGATION_FAILED,
)

if TYPE_CHECKING:
    from datetime import datetime

logger = get_logger(__name__)

_EMPTY = OrgEvolutionSummary()


class EvolutionSignalAggregator:
    """Aggregates evolution outcomes into org-wide summaries."""

    @property
    def domain(self) -> NotBlankStr:
        """Signal domain name."""
        return NotBlankStr("evolution")

    async def aggregate(
        self,
        *,
        since: datetime,
        until: datetime,
    ) -> OrgEvolutionSummary:
        """Aggregate evolution signals for the time window.

        Args:
            since: Start of observation window.
            until: End of observation window.

        Returns:
            Org-wide evolution summary.
        """
        _ = since, until  # Will be used by real implementation.
        try:
            logger.info(
                META_SIGNAL_AGGREGATION_COMPLETED,
                domain="evolution",
            )
        except Exception:
            logger.exception(
                META_SIGNAL_AGGREGATION_FAILED,
                domain="evolution",
            )
        return _EMPTY
