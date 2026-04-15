"""Scaling history signal aggregator (placeholder).

Will wrap the ScalingService to produce an OrgScalingSummary with
recent decisions and their outcomes. Currently returns an empty
summary until the real ScalingService integration is wired.
"""

from typing import TYPE_CHECKING

from synthorg.core.types import NotBlankStr
from synthorg.meta.models import OrgScalingSummary
from synthorg.observability import get_logger

if TYPE_CHECKING:
    from datetime import datetime

logger = get_logger(__name__)

_EMPTY = OrgScalingSummary()


class ScalingSignalAggregator:
    """Aggregates scaling decisions into org-wide summaries."""

    @property
    def domain(self) -> NotBlankStr:
        """Signal domain name."""
        return NotBlankStr("scaling")

    async def aggregate(
        self,
        *,
        since: datetime,
        until: datetime,
    ) -> OrgScalingSummary:
        """Aggregate scaling signals for the time window.

        Args:
            since: Start of observation window.
            until: End of observation window.

        Returns:
            Org-wide scaling summary.
        """
        _ = since, until  # Will be used by real implementation.
        logger.debug(
            "meta.signals.placeholder_skipped",
            domain="scaling",
        )
        return _EMPTY
