"""Unit tests for SQLiteProjectCostAggregateRepository."""

from typing import TYPE_CHECKING

import pytest

from synthorg.persistence.sqlite.project_cost_aggregate_repo import (
    SQLiteProjectCostAggregateRepository,
)

if TYPE_CHECKING:
    import aiosqlite


@pytest.mark.unit
class TestSQLiteProjectCostAggregateRepository:
    """Tests for the durable project cost aggregate repo."""

    async def test_get_returns_none_when_not_found(
        self,
        migrated_db: aiosqlite.Connection,
    ) -> None:
        repo = SQLiteProjectCostAggregateRepository(migrated_db)
        result = await repo.get("proj-nonexistent")
        assert result is None

    async def test_increment_creates_new_aggregate(
        self,
        migrated_db: aiosqlite.Connection,
    ) -> None:
        repo = SQLiteProjectCostAggregateRepository(migrated_db)
        agg = await repo.increment("proj-1", 1.5, 100, 50)

        assert agg.project_id == "proj-1"
        assert agg.total_cost == 1.5
        assert agg.total_input_tokens == 100
        assert agg.total_output_tokens == 50
        assert agg.record_count == 1

    async def test_increment_updates_existing(
        self,
        migrated_db: aiosqlite.Connection,
    ) -> None:
        repo = SQLiteProjectCostAggregateRepository(migrated_db)
        await repo.increment("proj-1", 1.0, 100, 50)
        agg = await repo.increment("proj-1", 2.0, 200, 100)

        assert agg.total_cost == pytest.approx(3.0)
        assert agg.total_input_tokens == 300
        assert agg.total_output_tokens == 150
        assert agg.record_count == 2

    async def test_multiple_increments_accumulate(
        self,
        migrated_db: aiosqlite.Connection,
    ) -> None:
        repo = SQLiteProjectCostAggregateRepository(migrated_db)
        for _ in range(5):
            await repo.increment("proj-1", 0.1, 10, 5)

        agg = await repo.get("proj-1")
        assert agg is not None
        assert agg.total_cost == pytest.approx(0.5)
        assert agg.total_input_tokens == 50
        assert agg.total_output_tokens == 25
        assert agg.record_count == 5

    async def test_get_after_increment(
        self,
        migrated_db: aiosqlite.Connection,
    ) -> None:
        repo = SQLiteProjectCostAggregateRepository(migrated_db)
        await repo.increment("proj-1", 3.0, 500, 200)

        agg = await repo.get("proj-1")
        assert agg is not None
        assert agg.total_cost == 3.0
        assert agg.total_input_tokens == 500
        assert agg.total_output_tokens == 200
        assert agg.record_count == 1

    async def test_isolation_between_projects(
        self,
        migrated_db: aiosqlite.Connection,
    ) -> None:
        repo = SQLiteProjectCostAggregateRepository(migrated_db)
        await repo.increment("proj-a", 10.0, 1000, 500)
        await repo.increment("proj-b", 5.0, 200, 100)

        agg_a = await repo.get("proj-a")
        agg_b = await repo.get("proj-b")

        assert agg_a is not None
        assert agg_b is not None
        assert agg_a.total_cost == 10.0
        assert agg_b.total_cost == 5.0

    async def test_last_updated_changes(
        self,
        migrated_db: aiosqlite.Connection,
    ) -> None:
        repo = SQLiteProjectCostAggregateRepository(migrated_db)
        agg1 = await repo.increment("proj-1", 1.0, 10, 5)
        agg2 = await repo.increment("proj-1", 1.0, 10, 5)

        assert agg2.last_updated >= agg1.last_updated
