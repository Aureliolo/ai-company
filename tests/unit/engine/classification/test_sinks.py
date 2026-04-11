"""Tests for classification downstream sinks."""

from unittest.mock import AsyncMock

import pytest

from synthorg.budget.coordination_config import ErrorCategory
from synthorg.engine.classification.models import (
    ClassificationResult,
    ErrorFinding,
    ErrorSeverity,
)
from synthorg.engine.classification.sinks import (
    NotificationDispatcherSink,
    PerformanceTrackerSink,
)
from synthorg.notifications.models import (
    NotificationCategory,
    NotificationSeverity,
)


def _finding(
    *,
    category: ErrorCategory = ErrorCategory.LOGICAL_CONTRADICTION,
    severity: ErrorSeverity = ErrorSeverity.HIGH,
    description: str = "Test finding",
) -> ErrorFinding:
    return ErrorFinding(
        category=category,
        severity=severity,
        description=description,
    )


def _classification_result(
    *findings: ErrorFinding,
) -> ClassificationResult:
    categories = tuple({f.category for f in findings})
    return ClassificationResult(
        execution_id="exec-1",
        agent_id="agent-1",
        task_id="task-1",
        categories_checked=categories or (ErrorCategory.LOGICAL_CONTRADICTION,),
        findings=findings,
    )


# ── PerformanceTrackerSink ─────────────────────────────────────


@pytest.mark.unit
class TestPerformanceTrackerSink:
    """PerformanceTrackerSink records collaboration events."""

    async def test_records_event_per_finding(self) -> None:
        tracker = AsyncMock()
        tracker.record_collaboration_event = AsyncMock()
        sink = PerformanceTrackerSink(tracker=tracker)

        result = _classification_result(
            _finding(description="Contradiction A"),
            _finding(description="Contradiction B"),
        )
        await sink.on_classification(result)

        assert tracker.record_collaboration_event.await_count == 2

    async def test_no_findings_skips(self) -> None:
        tracker = AsyncMock()
        tracker.record_collaboration_event = AsyncMock()
        sink = PerformanceTrackerSink(tracker=tracker)

        result = _classification_result()
        await sink.on_classification(result)

        tracker.record_collaboration_event.assert_not_awaited()

    async def test_tracker_error_swallowed(self) -> None:
        tracker = AsyncMock()
        tracker.record_collaboration_event = AsyncMock(
            side_effect=RuntimeError("tracker down"),
        )
        sink = PerformanceTrackerSink(tracker=tracker)

        result = _classification_result(_finding())
        # Should not raise
        await sink.on_classification(result)

    async def test_memory_error_propagates(self) -> None:
        tracker = AsyncMock()
        tracker.record_collaboration_event = AsyncMock(
            side_effect=MemoryError,
        )
        sink = PerformanceTrackerSink(tracker=tracker)

        result = _classification_result(_finding())
        with pytest.raises(MemoryError):
            await sink.on_classification(result)


# ── NotificationDispatcherSink ─────────────────────────────────


@pytest.mark.unit
class TestNotificationDispatcherSink:
    """NotificationDispatcherSink dispatches notifications."""

    async def test_dispatches_high_severity(self) -> None:
        dispatcher = AsyncMock()
        dispatcher.dispatch = AsyncMock()
        sink = NotificationDispatcherSink(dispatcher=dispatcher)

        result = _classification_result(
            _finding(severity=ErrorSeverity.HIGH),
        )
        await sink.on_classification(result)

        dispatcher.dispatch.assert_awaited_once()
        notification = dispatcher.dispatch.call_args[0][0]
        assert notification.severity == NotificationSeverity.ERROR
        assert notification.source == "engine.classification"

    async def test_filters_below_min_severity(self) -> None:
        dispatcher = AsyncMock()
        dispatcher.dispatch = AsyncMock()
        sink = NotificationDispatcherSink(dispatcher=dispatcher)

        result = _classification_result(
            _finding(severity=ErrorSeverity.LOW),
        )
        await sink.on_classification(result)

        dispatcher.dispatch.assert_not_awaited()

    async def test_custom_min_severity(self) -> None:
        dispatcher = AsyncMock()
        dispatcher.dispatch = AsyncMock()
        sink = NotificationDispatcherSink(
            dispatcher=dispatcher,
            min_severity=ErrorSeverity.MEDIUM,
        )

        result = _classification_result(
            _finding(severity=ErrorSeverity.MEDIUM),
        )
        await sink.on_classification(result)

        dispatcher.dispatch.assert_awaited_once()

    async def test_category_mapping(self) -> None:
        dispatcher = AsyncMock()
        dispatcher.dispatch = AsyncMock()
        sink = NotificationDispatcherSink(dispatcher=dispatcher)

        result = _classification_result(
            _finding(
                category=ErrorCategory.AUTHORITY_BREACH_ATTEMPT,
                severity=ErrorSeverity.HIGH,
            ),
        )
        await sink.on_classification(result)

        notification = dispatcher.dispatch.call_args[0][0]
        assert notification.category == NotificationCategory.SECURITY

    async def test_no_findings_skips(self) -> None:
        dispatcher = AsyncMock()
        dispatcher.dispatch = AsyncMock()
        sink = NotificationDispatcherSink(dispatcher=dispatcher)

        result = _classification_result()
        await sink.on_classification(result)

        dispatcher.dispatch.assert_not_awaited()

    async def test_dispatch_error_swallowed(self) -> None:
        dispatcher = AsyncMock()
        dispatcher.dispatch = AsyncMock(
            side_effect=RuntimeError("dispatch failed"),
        )
        sink = NotificationDispatcherSink(dispatcher=dispatcher)

        result = _classification_result(_finding())
        # Should not raise
        await sink.on_classification(result)

    async def test_memory_error_propagates(self) -> None:
        dispatcher = AsyncMock()
        dispatcher.dispatch = AsyncMock(side_effect=MemoryError)
        sink = NotificationDispatcherSink(dispatcher=dispatcher)

        result = _classification_result(_finding())
        with pytest.raises(MemoryError):
            await sink.on_classification(result)
