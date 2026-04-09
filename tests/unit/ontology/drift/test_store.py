"""Tests for SQLiteDriftReportStore."""

from collections.abc import AsyncGenerator

import aiosqlite
import pytest

from synthorg.ontology.drift.store import SQLiteDriftReportStore
from synthorg.ontology.models import AgentDrift, DriftAction, DriftReport


@pytest.fixture
async def store() -> AsyncGenerator[SQLiteDriftReportStore]:
    """Create an in-memory SQLite drift report store."""
    db = await aiosqlite.connect(":memory:")
    s = SQLiteDriftReportStore(db)
    await s.apply_schema()
    yield s
    await db.close()


def _make_report(
    entity_name: str = "Task",
    score: float = 0.3,
    *,
    version: int = 1,
) -> DriftReport:
    return DriftReport(
        entity_name=entity_name,
        divergence_score=score,
        canonical_version=version,
        recommendation=DriftAction.NOTIFY,
        divergent_agents=(
            AgentDrift(
                agent_id="agent-1",
                divergence_score=score,
                details="test drift",
            ),
        ),
    )


@pytest.mark.unit
class TestSQLiteDriftReportStore:
    """Tests for SQLiteDriftReportStore."""

    async def test_store_and_retrieve(
        self,
        store: SQLiteDriftReportStore,
    ) -> None:
        """Store and retrieve a drift report."""
        report = _make_report()
        await store.store_report(report)

        results = await store.get_latest("Task")
        assert len(results) == 1
        assert results[0].entity_name == "Task"
        assert results[0].divergence_score == 0.3
        assert results[0].recommendation == DriftAction.NOTIFY

    async def test_get_latest_ordered(
        self,
        store: SQLiteDriftReportStore,
    ) -> None:
        """Results are ordered by most recent first."""
        await store.store_report(_make_report(score=0.1))
        await store.store_report(_make_report(score=0.5))

        results = await store.get_latest("Task")
        assert len(results) == 2
        # Most recent first (ordered by recency, not score)
        assert results[0].divergence_score == 0.5

    async def test_get_latest_limit(
        self,
        store: SQLiteDriftReportStore,
    ) -> None:
        """Limit parameter restricts results."""
        for i in range(5):
            await store.store_report(_make_report(score=i * 0.1))

        results = await store.get_latest("Task", limit=2)
        assert len(results) == 2

    async def test_get_latest_filters_by_entity(
        self,
        store: SQLiteDriftReportStore,
    ) -> None:
        """Only returns reports for the specified entity."""
        await store.store_report(_make_report("Task"))
        await store.store_report(_make_report("Agent"))

        results = await store.get_latest("Task")
        assert len(results) == 1
        assert results[0].entity_name == "Task"

    async def test_get_all_latest(
        self,
        store: SQLiteDriftReportStore,
    ) -> None:
        """Returns latest report per entity."""
        await store.store_report(_make_report("Task", 0.2))
        await store.store_report(_make_report("Task", 0.5))
        await store.store_report(_make_report("Agent", 0.1))

        results = await store.get_all_latest()
        assert len(results) == 2
        names = {r.entity_name for r in results}
        assert names == {"Task", "Agent"}

    async def test_agents_persisted(
        self,
        store: SQLiteDriftReportStore,
    ) -> None:
        """Divergent agents are persisted and restored."""
        report = _make_report()
        await store.store_report(report)

        results = await store.get_latest("Task")
        assert len(results[0].divergent_agents) == 1
        assert results[0].divergent_agents[0].agent_id == "agent-1"

    async def test_empty_store(
        self,
        store: SQLiteDriftReportStore,
    ) -> None:
        """Empty store returns empty results."""
        results = await store.get_latest("Task")
        assert results == ()

        results = await store.get_all_latest()
        assert results == ()
