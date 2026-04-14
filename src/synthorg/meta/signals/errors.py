"""Error taxonomy signal aggregator.

Wraps the classification pipeline to produce an OrgErrorSummary
with category distributions and severity trends.
"""

from typing import TYPE_CHECKING

from synthorg.core.types import NotBlankStr
from synthorg.meta.models import OrgErrorSummary
from synthorg.observability import get_logger
from synthorg.observability.events.meta import (
    META_SIGNAL_AGGREGATION_COMPLETED,
    META_SIGNAL_AGGREGATION_FAILED,
)

if TYPE_CHECKING:
    from datetime import datetime

logger = get_logger(__name__)

_EMPTY = OrgErrorSummary()


class ErrorSignalAggregator:
    """Aggregates error taxonomy findings into org-wide summaries."""

    @property
    def domain(self) -> NotBlankStr:
        """Signal domain name."""
        return NotBlankStr("errors")

    async def aggregate(
        self,
        *,
        since: datetime,
        until: datetime,
    ) -> OrgErrorSummary:
        """Aggregate error signals for the time window.

        Args:
            since: Start of observation window.
            until: End of observation window.

        Returns:
            Org-wide error summary.
        """
        _ = since, until  # Will be used by real implementation.
        try:
            logger.info(
                META_SIGNAL_AGGREGATION_COMPLETED,
                domain="errors",
            )
        except Exception:
            logger.exception(
                META_SIGNAL_AGGREGATION_FAILED,
                domain="errors",
            )
        return _EMPTY
