"""Tests for CostTracker.get_provider_usage() method."""

from datetime import UTC, datetime

import pytest

from synthorg.budget.tracker import CostTracker, ProviderUsageSummary
from tests.unit.budget.conftest import make_cost_record


@pytest.mark.unit
class TestGetProviderUsage:
    """Tests for the get_provider_usage aggregation method."""

    async def test_empty_tracker_returns_zero(self) -> None:
        tracker = CostTracker()
        result = await tracker.get_provider_usage("test-provider")
        assert result == ProviderUsageSummary(total_tokens=0, total_cost=0.0)

    async def test_aggregates_tokens_and_cost_for_provider(self) -> None:
        tracker = CostTracker()
        await tracker.record(
            make_cost_record(
                provider="test-provider",
                input_tokens=1000,
                output_tokens=500,
                cost_usd=0.10,
            ),
        )
        await tracker.record(
            make_cost_record(
                provider="test-provider",
                input_tokens=2000,
                output_tokens=800,
                cost_usd=0.20,
            ),
        )

        result = await tracker.get_provider_usage("test-provider")
        assert result.total_tokens == 4300  # (1000+500) + (2000+800)
        assert result.total_cost == 0.30

    async def test_excludes_other_providers(self) -> None:
        tracker = CostTracker()
        await tracker.record(
            make_cost_record(
                provider="test-provider-a",
                input_tokens=1000,
                output_tokens=500,
                cost_usd=0.10,
            ),
        )
        await tracker.record(
            make_cost_record(
                provider="test-provider-b",
                input_tokens=9000,
                output_tokens=9000,
                cost_usd=9.99,
            ),
        )

        result = await tracker.get_provider_usage("test-provider-a")
        assert result.total_tokens == 1500
        assert result.total_cost == 0.10

    async def test_respects_time_range(self) -> None:
        tracker = CostTracker()
        t_old = datetime(2026, 2, 10, tzinfo=UTC)
        t_recent = datetime(2026, 2, 20, tzinfo=UTC)

        await tracker.record(
            make_cost_record(
                provider="test-provider",
                input_tokens=1000,
                output_tokens=500,
                cost_usd=0.10,
                timestamp=t_old,
            ),
        )
        await tracker.record(
            make_cost_record(
                provider="test-provider",
                input_tokens=2000,
                output_tokens=800,
                cost_usd=0.20,
                timestamp=t_recent,
            ),
        )

        result = await tracker.get_provider_usage(
            "test-provider",
            start=datetime(2026, 2, 15, tzinfo=UTC),
            end=datetime(2026, 2, 25, tzinfo=UTC),
        )
        assert result.total_tokens == 2800
        assert result.total_cost == 0.20

    async def test_invalid_time_range_raises(self) -> None:
        tracker = CostTracker()
        with pytest.raises(ValueError, match=r"start.*before end"):
            await tracker.get_provider_usage(
                "test-provider",
                start=datetime(2026, 3, 1, tzinfo=UTC),
                end=datetime(2026, 2, 1, tzinfo=UTC),
            )

    async def test_returns_named_tuple(self) -> None:
        tracker = CostTracker()
        result = await tracker.get_provider_usage("test-provider")
        assert isinstance(result, ProviderUsageSummary)
        assert result.total_tokens == 0
        assert result.total_cost == 0.0
