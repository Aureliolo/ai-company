"""Downstream classification sinks.

Implements ``ClassificationSink`` for wiring classification
results into the performance tracker and notification dispatcher.
"""

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from synthorg.budget.coordination_config import ErrorCategory
from synthorg.engine.classification.models import ErrorSeverity
from synthorg.hr.performance.models import CollaborationMetricRecord
from synthorg.notifications.models import (
    Notification,
    NotificationCategory,
    NotificationSeverity,
)
from synthorg.observability import get_logger
from synthorg.observability.events.classification import (
    CLASSIFICATION_SINK_ERROR,
)

if TYPE_CHECKING:
    from synthorg.engine.classification.models import ClassificationResult
    from synthorg.hr.performance.tracker import PerformanceTracker
    from synthorg.notifications.dispatcher import NotificationDispatcher

logger = get_logger(__name__)

_SEVERITY_MAP: dict[ErrorSeverity, NotificationSeverity] = {
    ErrorSeverity.HIGH: NotificationSeverity.ERROR,
    ErrorSeverity.MEDIUM: NotificationSeverity.WARNING,
    ErrorSeverity.LOW: NotificationSeverity.INFO,
}

_CATEGORY_MAP: dict[ErrorCategory, NotificationCategory] = {
    ErrorCategory.LOGICAL_CONTRADICTION: NotificationCategory.AGENT,
    ErrorCategory.NUMERICAL_DRIFT: NotificationCategory.AGENT,
    ErrorCategory.CONTEXT_OMISSION: NotificationCategory.AGENT,
    ErrorCategory.COORDINATION_FAILURE: NotificationCategory.SYSTEM,
    ErrorCategory.DELEGATION_PROTOCOL_VIOLATION: NotificationCategory.SECURITY,
    ErrorCategory.REVIEW_PIPELINE_VIOLATION: NotificationCategory.SECURITY,
    ErrorCategory.AUTHORITY_BREACH_ATTEMPT: NotificationCategory.SECURITY,
}

_SEVERITY_ORDER: dict[ErrorSeverity, int] = {
    ErrorSeverity.LOW: 0,
    ErrorSeverity.MEDIUM: 1,
    ErrorSeverity.HIGH: 2,
}


class PerformanceTrackerSink:
    """Forwards classification findings to the performance tracker.

    Records each finding as a collaboration event for the agent,
    enabling trend detection and evolution triggers.

    Args:
        tracker: The performance tracker to record events to.
    """

    def __init__(self, tracker: PerformanceTracker) -> None:
        self._tracker = tracker

    async def on_classification(
        self,
        result: ClassificationResult,
    ) -> None:
        """Record classification findings as collaboration events.

        Best-effort: logs errors internally, never raises
        (except MemoryError/RecursionError).

        Args:
            result: The completed classification result.
        """
        if not result.has_findings:
            return

        for finding in result.findings:
            try:
                record = CollaborationMetricRecord(
                    agent_id=result.agent_id,
                    recorded_at=datetime.now(UTC),
                    interaction_summary=(
                        f"[{finding.category.value}] {finding.description}"
                    ),
                )
                await self._tracker.record_collaboration_event(record)
            except MemoryError, RecursionError:
                raise
            except Exception:
                logger.exception(
                    CLASSIFICATION_SINK_ERROR,
                    agent_id=result.agent_id,
                    task_id=result.task_id,
                )


class NotificationDispatcherSink:
    """Forwards high-severity findings to the notification dispatcher.

    Converts ``ErrorFinding`` instances into ``Notification`` objects
    and dispatches them.  Only findings at or above ``min_severity``
    are dispatched.

    Args:
        dispatcher: The notification dispatcher.
        min_severity: Minimum severity to dispatch (default HIGH).
    """

    def __init__(
        self,
        dispatcher: NotificationDispatcher,
        *,
        min_severity: ErrorSeverity = ErrorSeverity.HIGH,
    ) -> None:
        self._dispatcher = dispatcher
        self._min_severity = min_severity
        self._min_rank = _SEVERITY_ORDER[min_severity]

    async def on_classification(
        self,
        result: ClassificationResult,
    ) -> None:
        """Dispatch notifications for high-severity findings.

        Best-effort: logs errors internally, never raises
        (except MemoryError/RecursionError).

        Args:
            result: The completed classification result.
        """
        if not result.has_findings:
            return

        for finding in result.findings:
            if _SEVERITY_ORDER[finding.severity] < self._min_rank:
                continue

            notification = Notification(
                category=_CATEGORY_MAP.get(
                    finding.category,
                    NotificationCategory.SYSTEM,
                ),
                severity=_SEVERITY_MAP.get(
                    finding.severity,
                    NotificationSeverity.WARNING,
                ),
                title=f"Classification: {finding.category.value}",
                body=finding.description,
                source="engine.classification",
                metadata={
                    "agent_id": result.agent_id,
                    "task_id": result.task_id,
                    "category": finding.category.value,
                    "severity": finding.severity.value,
                },
            )
            try:
                await self._dispatcher.dispatch(notification)
            except MemoryError, RecursionError:
                raise
            except Exception:
                logger.exception(
                    CLASSIFICATION_SINK_ERROR,
                    agent_id=result.agent_id,
                    task_id=result.task_id,
                )
