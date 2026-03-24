"""Tests for provider health tracking."""

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from synthorg.providers.health import (
    ProviderHealthRecord,
    ProviderHealthStatus,
    ProviderHealthSummary,
    ProviderHealthTracker,
)


def _make_record(
    *,
    provider_name: str = "test-provider",
    timestamp: datetime | None = None,
    success: bool = True,
    response_time_ms: float = 100.0,
    error_message: str | None = None,
) -> ProviderHealthRecord:
    """Build a ProviderHealthRecord with sensible defaults."""
    return ProviderHealthRecord(
        provider_name=provider_name,
        timestamp=timestamp or datetime.now(UTC),
        success=success,
        response_time_ms=response_time_ms,
        error_message=error_message,
    )


# ── Model tests ───────────────────────────────────────────────


@pytest.mark.unit
class TestProviderHealthRecord:
    def test_frozen(self) -> None:
        record = _make_record()
        with pytest.raises(ValidationError):
            record.provider_name = "other"  # type: ignore[misc]

    def test_success_record(self) -> None:
        record = _make_record(success=True, response_time_ms=42.5)
        assert record.success is True
        assert record.response_time_ms == 42.5
        assert record.error_message is None

    def test_error_record(self) -> None:
        record = _make_record(
            success=False,
            error_message="timeout",
        )
        assert record.success is False
        assert record.error_message == "timeout"

    def test_response_time_non_negative(self) -> None:
        with pytest.raises(ValueError, match="greater than or equal to 0"):
            _make_record(response_time_ms=-1.0)


@pytest.mark.unit
class TestProviderHealthSummary:
    def test_defaults(self) -> None:
        summary = ProviderHealthSummary()
        assert summary.health_status == ProviderHealthStatus.UP
        assert summary.last_check_timestamp is None
        assert summary.avg_response_time_ms is None
        assert summary.error_rate_percent_24h == 0.0
        assert summary.calls_last_24h == 0

    def test_frozen(self) -> None:
        summary = ProviderHealthSummary()
        with pytest.raises(ValidationError):
            summary.error_rate_percent_24h = 99.0  # type: ignore[misc]


# ── Tracker tests ─────────────────────────────────────────────


@pytest.mark.unit
class TestProviderHealthTracker:
    async def test_empty_summary(self) -> None:
        tracker = ProviderHealthTracker()
        summary = await tracker.get_summary("test-provider")
        assert summary.health_status == ProviderHealthStatus.UP
        assert summary.last_check_timestamp is None
        assert summary.avg_response_time_ms is None
        assert summary.error_rate_percent_24h == 0.0
        assert summary.calls_last_24h == 0

    async def test_single_success_record(self) -> None:
        tracker = ProviderHealthTracker()
        now = datetime.now(UTC)
        await tracker.record(
            _make_record(timestamp=now, response_time_ms=150.0),
        )
        summary = await tracker.get_summary("test-provider", now=now)
        assert summary.health_status == ProviderHealthStatus.UP
        assert summary.last_check_timestamp == now
        assert summary.avg_response_time_ms == 150.0
        assert summary.error_rate_percent_24h == 0.0
        assert summary.calls_last_24h == 1

    async def test_single_error_record(self) -> None:
        tracker = ProviderHealthTracker()
        now = datetime.now(UTC)
        await tracker.record(
            _make_record(
                timestamp=now,
                success=False,
                error_message="timeout",
            ),
        )
        summary = await tracker.get_summary("test-provider", now=now)
        assert summary.health_status == ProviderHealthStatus.DOWN
        assert summary.error_rate_percent_24h == 100.0
        assert summary.calls_last_24h == 1

    async def test_degraded_status(self) -> None:
        """Error rate >= 10% and < 50% -> DEGRADED."""
        tracker = ProviderHealthTracker()
        now = datetime.now(UTC)
        # 2 errors out of 10 calls = 20% error rate
        for i in range(10):
            await tracker.record(
                _make_record(
                    timestamp=now - timedelta(minutes=i),
                    success=i >= 2,
                    response_time_ms=100.0,
                ),
            )
        summary = await tracker.get_summary("test-provider", now=now)
        assert summary.health_status == ProviderHealthStatus.DEGRADED
        assert summary.error_rate_percent_24h == 20.0
        assert summary.calls_last_24h == 10

    async def test_down_status(self) -> None:
        """Error rate >= 50% -> DOWN."""
        tracker = ProviderHealthTracker()
        now = datetime.now(UTC)
        # 5 errors out of 10 calls = 50% error rate
        for i in range(10):
            await tracker.record(
                _make_record(
                    timestamp=now - timedelta(minutes=i),
                    success=i >= 5,
                    response_time_ms=100.0,
                ),
            )
        summary = await tracker.get_summary("test-provider", now=now)
        assert summary.health_status == ProviderHealthStatus.DOWN
        assert summary.error_rate_percent_24h == 50.0
        assert summary.calls_last_24h == 10

    async def test_up_status_low_error_rate(self) -> None:
        """Error rate < 10% -> UP."""
        tracker = ProviderHealthTracker()
        now = datetime.now(UTC)
        # 0 errors out of 20 calls = 0% error rate
        for i in range(20):
            await tracker.record(
                _make_record(
                    timestamp=now - timedelta(minutes=i),
                    response_time_ms=50.0 + i,
                ),
            )
        summary = await tracker.get_summary("test-provider", now=now)
        assert summary.health_status == ProviderHealthStatus.UP
        assert summary.error_rate_percent_24h == 0.0
        assert summary.calls_last_24h == 20

    async def test_24h_window_filtering(self) -> None:
        """Records older than 24h are excluded from summary."""
        tracker = ProviderHealthTracker()
        now = datetime.now(UTC)
        # Old record (25h ago) -- should be excluded
        await tracker.record(
            _make_record(
                timestamp=now - timedelta(hours=25),
                success=False,
            ),
        )
        # Recent record (1h ago) -- should be included
        await tracker.record(
            _make_record(
                timestamp=now - timedelta(hours=1),
                success=True,
                response_time_ms=200.0,
            ),
        )
        summary = await tracker.get_summary("test-provider", now=now)
        assert summary.calls_last_24h == 1
        assert summary.error_rate_percent_24h == 0.0
        assert summary.avg_response_time_ms == 200.0

    async def test_multiple_providers_isolated(self) -> None:
        """Each provider's health is tracked independently."""
        tracker = ProviderHealthTracker()
        now = datetime.now(UTC)
        await tracker.record(
            _make_record(
                provider_name="provider-a",
                timestamp=now,
                success=True,
                response_time_ms=100.0,
            ),
        )
        await tracker.record(
            _make_record(
                provider_name="provider-b",
                timestamp=now,
                success=False,
                response_time_ms=500.0,
            ),
        )
        summary_a = await tracker.get_summary("provider-a", now=now)
        summary_b = await tracker.get_summary("provider-b", now=now)

        assert summary_a.health_status == ProviderHealthStatus.UP
        assert summary_a.calls_last_24h == 1
        assert summary_b.health_status == ProviderHealthStatus.DOWN
        assert summary_b.calls_last_24h == 1

    async def test_avg_response_time(self) -> None:
        tracker = ProviderHealthTracker()
        now = datetime.now(UTC)
        await tracker.record(
            _make_record(timestamp=now, response_time_ms=100.0),
        )
        await tracker.record(
            _make_record(timestamp=now, response_time_ms=200.0),
        )
        await tracker.record(
            _make_record(timestamp=now, response_time_ms=300.0),
        )
        summary = await tracker.get_summary("test-provider", now=now)
        assert summary.avg_response_time_ms == 200.0

    async def test_last_check_timestamp(self) -> None:
        """last_check_timestamp is the most recent record timestamp."""
        tracker = ProviderHealthTracker()
        now = datetime.now(UTC)
        t1 = now - timedelta(hours=2)
        t2 = now - timedelta(hours=1)
        await tracker.record(_make_record(timestamp=t1))
        await tracker.record(_make_record(timestamp=t2))
        summary = await tracker.get_summary("test-provider", now=now)
        assert summary.last_check_timestamp == t2

    async def test_concurrent_record(self) -> None:
        """Concurrent record calls should not corrupt state."""
        tracker = ProviderHealthTracker()
        now = datetime.now(UTC)

        async def _record_batch(offset: int) -> None:
            for i in range(50):
                await tracker.record(
                    _make_record(
                        timestamp=now - timedelta(seconds=offset * 50 + i),
                        response_time_ms=float(i),
                    ),
                )

        async with asyncio.TaskGroup() as tg:
            for batch in range(4):
                tg.create_task(_record_batch(batch))

        summary = await tracker.get_summary("test-provider", now=now)
        assert summary.calls_last_24h == 200


# ── _derive_health_status boundary tests ──────────────────────


@pytest.mark.unit
class TestDeriveHealthStatus:
    """Test exact boundary values for health status thresholds."""

    @pytest.mark.parametrize(
        ("error_rate", "expected"),
        [
            (0.0, ProviderHealthStatus.UP),
            (9.99, ProviderHealthStatus.UP),
            (10.0, ProviderHealthStatus.DEGRADED),
            (49.99, ProviderHealthStatus.DEGRADED),
            (50.0, ProviderHealthStatus.DOWN),
            (100.0, ProviderHealthStatus.DOWN),
        ],
    )
    def test_boundary_values(
        self,
        error_rate: float,
        expected: ProviderHealthStatus,
    ) -> None:
        from synthorg.providers.health import _derive_health_status

        assert _derive_health_status(error_rate) == expected


# ── get_all_summaries tests ───────────────────────────────────


@pytest.mark.unit
class TestGetAllSummaries:
    async def test_empty_tracker(self) -> None:
        tracker = ProviderHealthTracker()
        result = await tracker.get_all_summaries()
        assert result == {}

    async def test_single_provider(self) -> None:
        tracker = ProviderHealthTracker()
        now = datetime.now(UTC)
        await tracker.record(
            _make_record(timestamp=now, response_time_ms=100.0),
        )
        result = await tracker.get_all_summaries(now=now)
        assert "test-provider" in result
        summary = result["test-provider"]
        assert summary.calls_last_24h == 1
        assert summary.health_status == ProviderHealthStatus.UP

    async def test_multiple_providers(self) -> None:
        tracker = ProviderHealthTracker()
        now = datetime.now(UTC)
        await tracker.record(
            _make_record(
                provider_name="provider-a",
                timestamp=now,
                success=True,
            ),
        )
        await tracker.record(
            _make_record(
                provider_name="provider-b",
                timestamp=now,
                success=False,
            ),
        )
        result = await tracker.get_all_summaries(now=now)
        assert len(result) == 2
        assert result["provider-a"].health_status == ProviderHealthStatus.UP
        assert result["provider-b"].health_status == ProviderHealthStatus.DOWN

    async def test_excludes_old_records(self) -> None:
        tracker = ProviderHealthTracker()
        now = datetime.now(UTC)
        await tracker.record(
            _make_record(
                timestamp=now - timedelta(hours=25),
                success=False,
            ),
        )
        result = await tracker.get_all_summaries(now=now)
        assert result == {}


# ── computed_field health_status tests ────────────────────────


@pytest.mark.unit
class TestHealthStatusComputed:
    def test_health_status_derived_from_error_rate(self) -> None:
        summary = ProviderHealthSummary(error_rate_percent_24h=15.0)
        assert summary.health_status == ProviderHealthStatus.DEGRADED

    def test_default_is_up(self) -> None:
        summary = ProviderHealthSummary()
        assert summary.health_status == ProviderHealthStatus.UP

    def test_down_at_50_percent(self) -> None:
        summary = ProviderHealthSummary(error_rate_percent_24h=50.0)
        assert summary.health_status == ProviderHealthStatus.DOWN


# ── cross-field validator tests ───────────────────────────────


@pytest.mark.unit
class TestRecordErrorConsistency:
    def test_success_with_error_message_rejected(self) -> None:
        with pytest.raises(
            ValidationError,
            match="error_message must be None when success is True",
        ):
            _make_record(success=True, error_message="oops")

    def test_failure_without_error_message_allowed(self) -> None:
        record = _make_record(success=False, error_message=None)
        assert record.success is False
        assert record.error_message is None

    def test_failure_with_error_message_allowed(self) -> None:
        record = _make_record(success=False, error_message="timeout")
        assert record.error_message == "timeout"


# ── prune_expired tests ──────────────────────────────────────


@pytest.mark.unit
class TestPruneExpired:
    async def test_prune_removes_old_records(self) -> None:
        tracker = ProviderHealthTracker()
        now = datetime.now(UTC)
        await tracker.record(
            _make_record(timestamp=now - timedelta(hours=25)),
        )
        await tracker.record(
            _make_record(timestamp=now - timedelta(hours=1)),
        )
        removed = await tracker.prune_expired(now=now)
        assert removed == 1
        summary = await tracker.get_summary("test-provider", now=now)
        assert summary.calls_last_24h == 1

    async def test_prune_empty_tracker(self) -> None:
        tracker = ProviderHealthTracker()
        removed = await tracker.prune_expired()
        assert removed == 0

    async def test_prune_nothing_expired(self) -> None:
        tracker = ProviderHealthTracker()
        now = datetime.now(UTC)
        await tracker.record(
            _make_record(timestamp=now - timedelta(hours=1)),
        )
        removed = await tracker.prune_expired(now=now)
        assert removed == 0
