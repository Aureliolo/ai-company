"""Unit tests for CostTracker project-level queries."""

from datetime import UTC, datetime, timedelta

import pytest

from synthorg.budget.cost_record import CostRecord
from synthorg.budget.tracker import CostTracker

from .conftest import make_cost_record


def _make_project_record(
    *,
    project_id: str = "proj-1",
    agent_id: str = "alice",
    task_id: str = "task-001",
    cost: float = 0.05,
    timestamp: datetime | None = None,
) -> CostRecord:
    """Build a CostRecord with project_id set."""
    return CostRecord(
        agent_id=agent_id,
        task_id=task_id,
        project_id=project_id,
        provider="test-provider",
        model="test-model-001",
        input_tokens=1000,
        output_tokens=500,
        cost=cost,
        timestamp=timestamp or datetime(2026, 2, 15, 12, 0, 0, tzinfo=UTC),
    )


@pytest.mark.unit
class TestGetProjectCost:
    """Tests for CostTracker.get_project_cost()."""

    async def test_empty_tracker_returns_zero(self, cost_tracker: CostTracker) -> None:
        result = await cost_tracker.get_project_cost("proj-1")
        assert result == 0.0

    async def test_single_project_record(self, cost_tracker: CostTracker) -> None:
        await cost_tracker.record(_make_project_record(cost=0.10))
        result = await cost_tracker.get_project_cost("proj-1")
        assert result == pytest.approx(0.10)

    async def test_filters_by_project(self, cost_tracker: CostTracker) -> None:
        await cost_tracker.record(_make_project_record(project_id="proj-1", cost=0.10))
        await cost_tracker.record(_make_project_record(project_id="proj-2", cost=0.20))
        await cost_tracker.record(_make_project_record(project_id="proj-1", cost=0.30))

        assert await cost_tracker.get_project_cost("proj-1") == pytest.approx(0.40)
        assert await cost_tracker.get_project_cost("proj-2") == pytest.approx(0.20)

    async def test_ignores_records_without_project_id(
        self, cost_tracker: CostTracker
    ) -> None:
        await cost_tracker.record(_make_project_record(project_id="proj-1", cost=0.10))
        # Record without project_id
        await cost_tracker.record(make_cost_record(cost=0.50))

        assert await cost_tracker.get_project_cost("proj-1") == pytest.approx(0.10)

    async def test_time_filtered(self, cost_tracker: CostTracker) -> None:
        base = datetime(2026, 3, 1, 12, 0, 0, tzinfo=UTC)
        await cost_tracker.record(
            _make_project_record(
                project_id="proj-1",
                cost=0.10,
                timestamp=base,
            )
        )
        await cost_tracker.record(
            _make_project_record(
                project_id="proj-1",
                cost=0.20,
                timestamp=base + timedelta(hours=2),
            )
        )

        result = await cost_tracker.get_project_cost(
            "proj-1",
            start=base + timedelta(hours=1),
        )
        assert result == pytest.approx(0.20)

    async def test_nonexistent_project_returns_zero(
        self, cost_tracker: CostTracker
    ) -> None:
        await cost_tracker.record(_make_project_record(project_id="proj-1", cost=0.10))
        assert await cost_tracker.get_project_cost("proj-999") == 0.0


@pytest.mark.unit
class TestGetProjectRecords:
    """Tests for CostTracker.get_project_records()."""

    async def test_returns_matching_records(self, cost_tracker: CostTracker) -> None:
        r1 = _make_project_record(project_id="proj-1", cost=0.10)
        r2 = _make_project_record(project_id="proj-2", cost=0.20)
        r3 = _make_project_record(project_id="proj-1", cost=0.30)
        await cost_tracker.record(r1)
        await cost_tracker.record(r2)
        await cost_tracker.record(r3)

        records = await cost_tracker.get_project_records("proj-1")
        assert len(records) == 2
        costs = sorted(r.cost for r in records)
        assert costs == pytest.approx([0.10, 0.30])

    async def test_empty_for_unknown_project(self, cost_tracker: CostTracker) -> None:
        await cost_tracker.record(_make_project_record(project_id="proj-1"))
        records = await cost_tracker.get_project_records("proj-999")
        assert records == ()

    async def test_time_filtered(self, cost_tracker: CostTracker) -> None:
        base = datetime(2026, 3, 1, 12, 0, 0, tzinfo=UTC)
        await cost_tracker.record(
            _make_project_record(
                project_id="proj-1",
                cost=0.10,
                timestamp=base,
            )
        )
        await cost_tracker.record(
            _make_project_record(
                project_id="proj-1",
                cost=0.20,
                timestamp=base + timedelta(hours=2),
            )
        )

        records = await cost_tracker.get_project_records(
            "proj-1",
            start=base + timedelta(hours=1),
        )
        assert len(records) == 1
        assert records[0].cost == pytest.approx(0.20)
