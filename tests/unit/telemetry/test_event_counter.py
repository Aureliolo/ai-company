"""Tests for the in-memory telemetry event counter."""

from datetime import UTC, datetime, timedelta

import pytest

from synthorg.core.types import NotBlankStr
from synthorg.telemetry.event_counter import InMemoryTelemetryEventCounter
from synthorg.telemetry.event_counter_protocol import (
    TelemetryEventCounter,
    TelemetrySubscriber,
)
from synthorg.telemetry.protocol import TelemetryEvent


def _event(
    *,
    event_type: str = "deployment.startup",
    timestamp: datetime | None = None,
) -> TelemetryEvent:
    return TelemetryEvent(
        event_type=NotBlankStr(event_type),
        deployment_id=NotBlankStr("dep-id"),
        synthorg_version=NotBlankStr("0.0.0"),
        python_version=NotBlankStr("3.14"),
        os_platform=NotBlankStr("linux"),
        timestamp=timestamp or datetime.now(UTC),
    )


@pytest.mark.unit
class TestInMemoryTelemetryEventCounterProtocol:
    """The in-memory impl satisfies both protocols."""

    def test_satisfies_counter_protocol(self) -> None:
        assert isinstance(InMemoryTelemetryEventCounter(), TelemetryEventCounter)

    def test_satisfies_subscriber_protocol(self) -> None:
        assert isinstance(InMemoryTelemetryEventCounter(), TelemetrySubscriber)


@pytest.mark.unit
class TestInMemoryTelemetryEventCounterCapacity:
    """Ring-buffer bounds and eviction."""

    def test_rejects_non_positive_capacity(self) -> None:
        with pytest.raises(ValueError, match="max_events must be >= 1"):
            InMemoryTelemetryEventCounter(max_events=0)

    async def test_evicts_oldest_when_full(self) -> None:
        counter = InMemoryTelemetryEventCounter(max_events=3)
        now = datetime.now(UTC)
        for idx in range(5):
            counter.on_event(
                _event(
                    event_type=f"evt-{idx}",
                    timestamp=now + timedelta(seconds=idx),
                ),
            )
        assert await counter.count() == 3

    async def test_clear_resets(self) -> None:
        counter = InMemoryTelemetryEventCounter()
        counter.on_event(_event())
        assert await counter.count() == 1
        await counter.clear()
        assert await counter.count() == 0


@pytest.mark.unit
class TestInMemoryTelemetryEventCounterSummarize:
    """summarize filters by window and ranks event types."""

    async def test_empty_summary_when_no_events(self) -> None:
        counter = InMemoryTelemetryEventCounter()
        now = datetime.now(UTC)
        summary = await counter.summarize(
            since=now - timedelta(hours=1),
            until=now,
        )
        assert summary.event_count == 0
        assert summary.top_event_types == ()
        assert summary.error_event_count == 0

    async def test_filters_by_window(self) -> None:
        counter = InMemoryTelemetryEventCounter()
        now = datetime.now(UTC)
        counter.on_event(
            _event(timestamp=now - timedelta(hours=2)),  # out of window
        )
        counter.on_event(
            _event(timestamp=now - timedelta(minutes=15)),  # in window
        )
        summary = await counter.summarize(
            since=now - timedelta(hours=1),
            until=now,
        )
        assert summary.event_count == 1

    async def test_counts_errors_via_name_hint(self) -> None:
        counter = InMemoryTelemetryEventCounter()
        now = datetime.now(UTC)
        ts = now - timedelta(minutes=5)
        counter.on_event(_event(event_type="deployment.startup", timestamp=ts))
        counter.on_event(
            _event(event_type="telemetry.report.failed", timestamp=ts),
        )
        counter.on_event(
            _event(event_type="http.request.rejected", timestamp=ts),
        )
        summary = await counter.summarize(
            since=now - timedelta(hours=1),
            until=now + timedelta(minutes=1),
        )
        assert summary.event_count == 3
        assert summary.error_event_count == 2

    async def test_top_types_ranked_by_count(self) -> None:
        counter = InMemoryTelemetryEventCounter()
        now = datetime.now(UTC)
        ts = now - timedelta(minutes=5)
        for _ in range(3):
            counter.on_event(_event(event_type="common", timestamp=ts))
        counter.on_event(_event(event_type="rare", timestamp=ts))
        summary = await counter.summarize(
            since=now - timedelta(hours=1),
            until=now + timedelta(minutes=1),
            max_top=5,
        )
        assert summary.top_event_types[0] == "common"
        assert summary.top_event_types[1] == "rare"

    async def test_rejects_inverted_window(self) -> None:
        counter = InMemoryTelemetryEventCounter()
        now = datetime.now(UTC)
        with pytest.raises(ValueError, match="earlier"):
            await counter.summarize(since=now, until=now - timedelta(hours=1))

    async def test_rejects_invalid_max_top(self) -> None:
        counter = InMemoryTelemetryEventCounter()
        now = datetime.now(UTC)
        with pytest.raises(ValueError, match="max_top"):
            await counter.summarize(
                since=now - timedelta(hours=1),
                until=now,
                max_top=0,
            )
