"""MVCC-specific tests for SQLiteOrgFactStore.

Tests the append-only operation log, version counter, materialized
snapshot, time-travel queries, and audit trail.
"""

import asyncio
import unittest.mock
from datetime import UTC, datetime, timedelta

import pytest

from synthorg.core.enums import OrgFactCategory, SeniorityLevel
from synthorg.memory.org.errors import OrgMemoryConnectionError
from synthorg.memory.org.models import OrgFactAuthor
from synthorg.memory.org.sqlite_store import SQLiteOrgFactStore

# Import conftest fixtures and helpers
from .conftest import (
    AGENT_AUTHOR,
    HUMAN_AUTHOR,
    _make_fact,
)


@pytest.mark.unit
class TestMvccSchema:
    """MVCC tables are created on connect."""

    async def test_tables_created(self, connected_store) -> None:
        assert connected_store._db is not None
        cursor = await connected_store._db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name IN "
            "('org_facts_operation_log', 'org_facts_snapshot') "
            "ORDER BY name",
        )
        tables = [row[0] for row in await cursor.fetchall()]
        assert tables == [
            "org_facts_operation_log",
            "org_facts_snapshot",
        ]


@pytest.mark.unit
class TestMvccPublish:
    """Append-only publish (save) semantics."""

    async def test_save_creates_log_entry(self, connected_store) -> None:
        await connected_store.save(_make_fact("f1"))
        log = await connected_store.get_operation_log("f1")
        assert len(log) == 1
        assert log[0].operation_type == "PUBLISH"
        assert log[0].fact_id == "f1"
        assert log[0].version == 1
        assert log[0].content == "Test fact"

    async def test_save_creates_snapshot(self, connected_store) -> None:
        await connected_store.save(_make_fact("f1"))
        fact = await connected_store.get("f1")
        assert fact is not None
        assert fact.id == "f1"
        assert fact.content == "Test fact"

    async def test_republish_increments_version(self, connected_store) -> None:
        await connected_store.save(_make_fact("f1", "v1 content"))
        await connected_store.save(_make_fact("f1", "v2 content"))
        log = await connected_store.get_operation_log("f1")
        assert len(log) == 2
        assert log[0].version == 1
        assert log[0].content == "v1 content"
        assert log[1].version == 2
        assert log[1].content == "v2 content"
        fact = await connected_store.get("f1")
        assert fact is not None
        assert fact.content == "v2 content"

    async def test_save_with_agent_author_records_autonomy(
        self, connected_store
    ) -> None:
        from synthorg.core.enums import AutonomyLevel

        await connected_store.save(_make_fact("f1", author=AGENT_AUTHOR))
        log = await connected_store.get_operation_log("f1")
        assert log[0].author_agent_id == "agent-1"
        assert log[0].author_autonomy_level == AutonomyLevel.SEMI

    async def test_save_with_tags_records_in_log(self, connected_store) -> None:
        await connected_store.save(
            _make_fact("f1", tags=("security", "core-policy")),
        )
        log = await connected_store.get_operation_log("f1")
        assert log[0].tags == ("core-policy", "security")


@pytest.mark.unit
class TestMvccRetract:
    """Append-only retract (delete) semantics."""

    async def test_retract_creates_log_entry(self, connected_store) -> None:
        await connected_store.save(_make_fact("f1"))
        assert await connected_store.delete("f1", author=HUMAN_AUTHOR) is True
        log = await connected_store.get_operation_log("f1")
        assert len(log) == 2
        assert log[0].operation_type == "PUBLISH"
        assert log[1].operation_type == "RETRACT"
        assert log[1].version == 2
        assert log[1].content is None

    async def test_retract_marks_snapshot(self, connected_store) -> None:
        await connected_store.save(_make_fact("f1"))
        await connected_store.delete("f1", author=HUMAN_AUTHOR)
        assert await connected_store.get("f1") is None

    async def test_retract_already_retracted_returns_false(
        self, connected_store
    ) -> None:
        await connected_store.save(_make_fact("f1"))
        assert await connected_store.delete("f1", author=HUMAN_AUTHOR) is True
        assert await connected_store.delete("f1", author=HUMAN_AUTHOR) is False

    async def test_retract_nonexistent_returns_false(self, connected_store) -> None:
        assert await connected_store.delete("nonexistent", author=HUMAN_AUTHOR) is False


@pytest.mark.unit
class TestMvccReadFiltering:
    """Reads exclude retracted facts."""

    async def test_get_excludes_retracted(self, connected_store) -> None:
        await connected_store.save(_make_fact("f1"))
        await connected_store.delete("f1", author=HUMAN_AUTHOR)
        assert await connected_store.get("f1") is None

    async def test_query_excludes_retracted(self, connected_store) -> None:
        await connected_store.save(_make_fact("f1", "Active fact"))
        await connected_store.save(_make_fact("f2", "Retracted fact"))
        await connected_store.delete("f2", author=HUMAN_AUTHOR)
        results = await connected_store.query(limit=10)
        ids = [f.id for f in results]
        assert "f1" in ids
        assert "f2" not in ids

    async def test_list_by_category_excludes_retracted(self, connected_store) -> None:
        await connected_store.save(
            _make_fact("f1", category=OrgFactCategory.ADR),
        )
        await connected_store.save(
            _make_fact("f2", category=OrgFactCategory.ADR),
        )
        await connected_store.delete("f1", author=HUMAN_AUTHOR)
        results = await connected_store.list_by_category(OrgFactCategory.ADR)
        assert len(results) == 1
        assert results[0].id == "f2"


@pytest.mark.unit
class TestMvccVersionCounter:
    """Version counter is per-fact and monotonic."""

    async def test_independent_fact_versions(self, connected_store) -> None:
        await connected_store.save(_make_fact("f1", "First fact"))
        await connected_store.save(_make_fact("f2", "Second fact"))
        log_f1 = await connected_store.get_operation_log("f1")
        log_f2 = await connected_store.get_operation_log("f2")
        assert log_f1[0].version == 1
        assert log_f2[0].version == 1

    async def test_version_increments_across_operations(self, connected_store) -> None:
        await connected_store.save(_make_fact("f1", "v1"))
        await connected_store.save(_make_fact("f1", "v2"))
        await connected_store.delete("f1", author=HUMAN_AUTHOR)
        log = await connected_store.get_operation_log("f1")
        assert [e.version for e in log] == [1, 2, 3]


@pytest.mark.unit
class TestMvccSnapshotAt:
    """Time-travel queries via snapshot_at()."""

    async def test_snapshot_before_any_operations(self, connected_store) -> None:
        past = datetime.now(UTC) - timedelta(hours=1)
        await connected_store.save(_make_fact("f1"))
        snapshot = await connected_store.snapshot_at(past)
        assert len(snapshot) == 0

    async def test_snapshot_after_publish(self, connected_store) -> None:
        await connected_store.save(_make_fact("f1", "Published fact"))
        future = datetime.now(UTC) + timedelta(hours=1)
        snapshot = await connected_store.snapshot_at(future)
        assert len(snapshot) == 1
        assert snapshot[0].fact_id == "f1"
        assert snapshot[0].content == "Published fact"
        assert snapshot[0].retracted_at is None

    async def test_snapshot_after_retract(self, connected_store) -> None:
        await connected_store.save(_make_fact("f1"))
        await connected_store.delete("f1", author=HUMAN_AUTHOR)
        future = datetime.now(UTC) + timedelta(hours=1)
        snapshot = await connected_store.snapshot_at(future)
        assert len(snapshot) == 1
        assert snapshot[0].fact_id == "f1"
        assert snapshot[0].retracted_at is not None

    async def test_snapshot_between_publish_and_retract(self, connected_store) -> None:
        """Snapshot at a time between publish and retract shows active fact."""
        t_publish = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)
        t_retract = datetime(2026, 1, 1, 0, 0, 2, tzinfo=UTC)
        mid_ts = datetime(2026, 1, 1, 0, 0, 1, tzinfo=UTC)
        call_count = 0
        timestamps = [t_publish, t_retract]

        def _fake_now(_tz=None):
            nonlocal call_count
            ts = timestamps[min(call_count, len(timestamps) - 1)]
            call_count += 1
            return ts

        with unittest.mock.patch(
            "synthorg.memory.org.sqlite_store.datetime",
        ) as mock_dt:
            mock_dt.now = _fake_now
            mock_dt.fromisoformat = datetime.fromisoformat
            await connected_store.save(_make_fact("f1"))
            await connected_store.delete("f1", author=HUMAN_AUTHOR)

        snapshot = await connected_store.snapshot_at(mid_ts)
        assert len(snapshot) == 1
        assert snapshot[0].retracted_at is None

    async def test_snapshot_at_when_not_connected(self) -> None:
        store = SQLiteOrgFactStore(":memory:")
        with pytest.raises(OrgMemoryConnectionError):
            await store.snapshot_at(datetime.now(UTC))


@pytest.mark.unit
class TestMvccGetOperationLog:
    """Audit trail via get_operation_log()."""

    async def test_full_audit_trail(self, connected_store) -> None:
        await connected_store.save(_make_fact("f1", "Original"))
        await connected_store.save(_make_fact("f1", "Updated"))
        await connected_store.delete("f1", author=HUMAN_AUTHOR)
        log = await connected_store.get_operation_log("f1")
        assert len(log) == 3
        assert log[0].operation_type == "PUBLISH"
        assert log[0].content == "Original"
        assert log[1].operation_type == "PUBLISH"
        assert log[1].content == "Updated"
        assert log[2].operation_type == "RETRACT"
        assert log[2].content is None
        assert [e.version for e in log] == [1, 2, 3]

    async def test_empty_log_for_unknown_fact(self, connected_store) -> None:
        log = await connected_store.get_operation_log("nonexistent")
        assert log == ()

    async def test_log_when_not_connected(self) -> None:
        store = SQLiteOrgFactStore(":memory:")
        with pytest.raises(OrgMemoryConnectionError):
            await store.get_operation_log("f1")

    async def test_log_preserves_all_operations(self, connected_store) -> None:
        """Even after retraction, all operations are preserved."""
        await connected_store.save(
            _make_fact("f1", "v1", tags=("tag-a",)),
        )
        await connected_store.save(
            _make_fact("f1", "v2", tags=("tag-b",)),
        )
        await connected_store.delete("f1", author=HUMAN_AUTHOR)
        log = await connected_store.get_operation_log("f1")
        assert log[0].tags == ("tag-a",)
        assert log[1].tags == ("tag-b",)
        assert log[2].tags == ()


@pytest.mark.unit
class TestMvccConcurrentPublishes:
    """Two agents publishing the same fact_id concurrently."""

    async def test_both_operations_in_log(self, tmp_path) -> None:
        db_path = str(tmp_path / "concurrent.db")
        store_a = SQLiteOrgFactStore(db_path)
        store_b = SQLiteOrgFactStore(db_path)
        await store_a.connect()
        await store_b.connect()
        try:
            agent_a = OrgFactAuthor(
                agent_id="agent-a",
                seniority=SeniorityLevel.SENIOR,
                is_human=False,
            )
            agent_b = OrgFactAuthor(
                agent_id="agent-b",
                seniority=SeniorityLevel.LEAD,
                is_human=False,
            )
            await asyncio.gather(
                store_a.save(
                    _make_fact("shared-fact", "Agent A version", author=agent_a),
                ),
                store_b.save(
                    _make_fact("shared-fact", "Agent B version", author=agent_b),
                ),
            )
            log = await store_a.get_operation_log("shared-fact")
            assert len(log) == 2
            agent_ids = {e.author_agent_id for e in log}
            assert agent_ids == {"agent-a", "agent-b"}
            # Snapshot has last writer wins
            fact = await store_a.get("shared-fact")
            assert fact is not None
        finally:
            await store_a.disconnect()
            await store_b.disconnect()
