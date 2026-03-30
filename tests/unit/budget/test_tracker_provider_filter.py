"""Tests for CostTracker provider-level filtering."""

from datetime import UTC, datetime

import pytest

from synthorg.budget.tracker import CostTracker
from tests.unit.budget.conftest import make_cost_record


@pytest.mark.unit
class TestGetRecordsProviderFilter:
    """Tests for the provider parameter in get_records()."""

    async def test_filter_by_provider(self) -> None:
        tracker = CostTracker()
        await tracker.record(make_cost_record(provider="test-provider-a"))
        await tracker.record(make_cost_record(provider="test-provider-b"))

        result = await tracker.get_records(provider="test-provider-a")
        assert len(result) == 1
        assert result[0].provider == "test-provider-a"

    async def test_provider_filter_returns_empty_for_unknown(self) -> None:
        tracker = CostTracker()
        await tracker.record(make_cost_record(provider="test-provider-a"))

        result = await tracker.get_records(provider="nonexistent")
        assert result == ()

    async def test_provider_filter_combined_with_agent_id(self) -> None:
        tracker = CostTracker()
        await tracker.record(
            make_cost_record(agent_id="alice", provider="test-provider-a"),
        )
        await tracker.record(
            make_cost_record(agent_id="alice", provider="test-provider-b"),
        )
        await tracker.record(
            make_cost_record(agent_id="bob", provider="test-provider-a"),
        )

        result = await tracker.get_records(
            agent_id="alice",
            provider="test-provider-a",
        )
        assert len(result) == 1
        assert result[0].agent_id == "alice"
        assert result[0].provider == "test-provider-a"

    async def test_provider_filter_combined_with_time_range(self) -> None:
        tracker = CostTracker()
        t1 = datetime(2026, 2, 10, tzinfo=UTC)
        t2 = datetime(2026, 2, 20, tzinfo=UTC)
        await tracker.record(
            make_cost_record(provider="test-provider-a", timestamp=t1),
        )
        await tracker.record(
            make_cost_record(provider="test-provider-a", timestamp=t2),
        )
        await tracker.record(
            make_cost_record(provider="test-provider-b", timestamp=t2),
        )

        result = await tracker.get_records(
            provider="test-provider-a",
            start=datetime(2026, 2, 15, tzinfo=UTC),
            end=datetime(2026, 2, 25, tzinfo=UTC),
        )
        assert len(result) == 1
        assert result[0].provider == "test-provider-a"
        assert result[0].timestamp == t2

    async def test_none_provider_returns_all(self) -> None:
        """Passing provider=None (default) returns all records."""
        tracker = CostTracker()
        await tracker.record(make_cost_record(provider="test-provider-a"))
        await tracker.record(make_cost_record(provider="test-provider-b"))

        result = await tracker.get_records(provider=None)
        assert len(result) == 2
