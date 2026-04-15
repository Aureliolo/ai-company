"""Proactive alert service for org-level inflections.

Implements ``OrgInflectionSink`` to receive inflection events
from the monitor and converts them to ``Alert`` objects when
severity meets the configured threshold.
"""

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from synthorg.meta.chief_of_staff.events import (
    COS_ALERT_EMITTED,
    COS_ALERT_SUPPRESSED,
)
from synthorg.meta.chief_of_staff.models import Alert, OrgInflection
from synthorg.meta.models import RuleSeverity
from synthorg.observability import get_logger

if TYPE_CHECKING:
    from synthorg.meta.chief_of_staff.protocol import AlertSink

logger = get_logger(__name__)

_SEVERITY_ORDER: dict[RuleSeverity, int] = {
    RuleSeverity.INFO: 0,
    RuleSeverity.WARNING: 1,
    RuleSeverity.CRITICAL: 2,
}


class ProactiveAlertService:
    """Converts org-level inflections into proactive alerts.

    Filters by severity threshold and emits alerts to
    registered ``AlertSink`` consumers.

    Args:
        alert_sinks: Consumers of proactive alerts.
        severity_threshold: Minimum severity to emit an alert.
    """

    def __init__(
        self,
        *,
        alert_sinks: tuple[AlertSink, ...] = (),
        severity_threshold: RuleSeverity = RuleSeverity.WARNING,
    ) -> None:
        self._sinks = alert_sinks
        self._threshold = severity_threshold

    async def on_inflection(self, inflection: OrgInflection) -> None:
        """Receive an org-level inflection event.

        Creates and emits an ``Alert`` if the inflection's
        severity meets or exceeds the configured threshold.

        Args:
            inflection: The detected inflection.
        """
        if _SEVERITY_ORDER.get(
            inflection.severity,
            0,
        ) < _SEVERITY_ORDER.get(self._threshold, 1):
            logger.debug(
                COS_ALERT_SUPPRESSED,
                metric=inflection.metric_name,
                severity=inflection.severity.value,
                threshold=self._threshold.value,
            )
            return
        alert = Alert(
            severity=inflection.severity,
            alert_type="inflection",
            description=inflection.description,
            affected_domains=inflection.affected_domains,
            signal_context={
                "metric": inflection.metric_name,
                "old_value": inflection.old_value,
                "new_value": inflection.new_value,
                "change_ratio": inflection.change_ratio,
            },
            emitted_at=datetime.now(UTC),
        )
        for sink in self._sinks:
            await sink.on_alert(alert)
        logger.info(
            COS_ALERT_EMITTED,
            alert_id=str(alert.id),
            severity=alert.severity.value,
            metric=inflection.metric_name,
        )


class LoggingAlertSink:
    """Alert sink that logs alerts via structured logging.

    Uses WARNING for WARNING-level alerts and ERROR for
    CRITICAL-level alerts.
    """

    async def on_alert(self, alert: Alert) -> None:
        """Log the alert at the appropriate level.

        Args:
            alert: The alert to log.
        """
        level = "error" if alert.severity is RuleSeverity.CRITICAL else "warning"
        getattr(logger, level)(
            COS_ALERT_EMITTED,
            alert_id=str(alert.id),
            alert_type=alert.alert_type,
            severity=alert.severity.value,
            description=alert.description,
            domains=list(alert.affected_domains),
        )
