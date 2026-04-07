"""MVCC-specific tests for SQLiteOrgFactStore.

Tests the append-only operation log, version counter, materialized
snapshot, time-travel queries, and audit trail.
"""

import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from synthorg.core.enums import (
    AutonomyLevel,
    OrgFactCategory,
    SeniorityLevel,
)
from synthorg.memory.org.errors import OrgMemoryConnectionError
from synthorg.memory.org.models import OrgFact, OrgFactAuthor
from synthorg.memory.org.store import SQLiteOrgFactStore

_NOW = datetime.now(UTC)
_HUMAN_AUTHOR = OrgFactAuthor(is_human=True)
_AGENT_AUTHOR = OrgFactAuthor(
    agent_id="agent-1",
    seniority=SeniorityLevel.SENIOR,
    autonomy_level=AutonomyLevel.SEMI,
    is_human=False,
)


def _make_fact(
    fact_id: str = "fact-1",
    content: str = "Test fact",
    category: OrgFactCategory = OrgFactCategory.ADR,
    *,
    author: OrgFactAuthor = _HUMAN_AUTHOR,
    tags: tuple[str, ...] = (),
) -> OrgFact:
    return OrgFact(
        id=fact_id,
        content=content,
        category=category,
        tags=tags,
        author=author,
        created_at=_NOW,
    )


@pytest.mark.unit
class TestMvccSchema:
    """MVCC tables are created on connect."""

    async def test_tables_created(self) -> None:
        store = SQLiteOrgFactStore(":memory:")
        await store.connect()
        try:
            assert store._db is not None
            cursor = await store._db.execute(
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
        finally:
            await store.disconnect()


@pytest.mark.unit
class TestMvccPublish:
    """Append-only publish (save) semantics."""

    async def test_save_creates_log_entry(self) -> None:
        store = SQLiteOrgFactStore(":memory:")
        await store.connect()
        try:
            await store.save(_make_fact("f1"))
            log = await store.get_operation_log("f1")
            assert len(log) == 1
            assert log[0].operation_type == "PUBLISH"
            assert log[0].fact_id == "f1"
            assert log[0].version == 1
            assert log[0].content == "Test fact"
        finally:
            await store.disconnect()

    async def test_save_creates_snapshot(self) -> None:
        store = SQLiteOrgFactStore(":memory:")
        await store.connect()
        try:
            await store.save(_make_fact("f1"))
            fact = await store.get("f1")
            assert fact is not None
            assert fact.id == "f1"
            assert fact.content == "Test fact"
        finally:
            await store.disconnect()

    async def test_republish_increments_version(self) -> None:
        store = SQLiteOrgFactStore(":memory:")
        await store.connect()
        try:
            await store.save(_make_fact("f1", "v1 content"))
            await store.save(_make_fact("f1", "v2 content"))
            log = await store.get_operation_log("f1")
            assert len(log) == 2
            assert log[0].version == 1
            assert log[0].content == "v1 content"
            assert log[1].version == 2
            assert log[1].content == "v2 content"
            fact = await store.get("f1")
            assert fact is not None
            assert fact.content == "v2 content"
        finally:
            await store.disconnect()

    async def test_save_with_agent_author_records_autonomy(self) -> None:
        store = SQLiteOrgFactStore(":memory:")
        await store.connect()
        try:
            await store.save(_make_fact("f1", author=_AGENT_AUTHOR))
            log = await store.get_operation_log("f1")
            assert log[0].author_agent_id == "agent-1"
            assert log[0].author_autonomy_level == AutonomyLevel.SEMI
        finally:
            await store.disconnect()

    async def test_save_with_tags_records_in_log(self) -> None:
        store = SQLiteOrgFactStore(":memory:")
        await store.connect()
        try:
            await store.save(
                _make_fact("f1", tags=("security", "core-policy")),
            )
            log = await store.get_operation_log("f1")
            assert set(log[0].tags) == {"security", "core-policy"}
        finally:
            await store.disconnect()


@pytest.mark.unit
class TestMvccRetract:
    """Append-only retract (delete) semantics."""

    async def test_retract_creates_log_entry(self) -> None:
        store = SQLiteOrgFactStore(":memory:")
        await store.connect()
        try:
            await store.save(_make_fact("f1"))
            assert await store.delete("f1") is True
            log = await store.get_operation_log("f1")
            assert len(log) == 2
            assert log[0].operation_type == "PUBLISH"
            assert log[1].operation_type == "RETRACT"
            assert log[1].version == 2
            assert log[1].content is None
        finally:
            await store.disconnect()

    async def test_retract_marks_snapshot(self) -> None:
        store = SQLiteOrgFactStore(":memory:")
        await store.connect()
        try:
            await store.save(_make_fact("f1"))
            await store.delete("f1")
            assert await store.get("f1") is None
        finally:
            await store.disconnect()

    async def test_retract_already_retracted_returns_false(self) -> None:
        store = SQLiteOrgFactStore(":memory:")
        await store.connect()
        try:
            await store.save(_make_fact("f1"))
            assert await store.delete("f1") is True
            assert await store.delete("f1") is False
        finally:
            await store.disconnect()

    async def test_retract_nonexistent_returns_false(self) -> None:
        store = SQLiteOrgFactStore(":memory:")
        await store.connect()
        try:
            assert await store.delete("nonexistent") is False
        finally:
            await store.disconnect()


@pytest.mark.unit
class TestMvccReadFiltering:
    """Reads exclude retracted facts."""

    async def test_get_excludes_retracted(self) -> None:
        store = SQLiteOrgFactStore(":memory:")
        await store.connect()
        try:
            await store.save(_make_fact("f1"))
            await store.delete("f1")
            assert await store.get("f1") is None
        finally:
            await store.disconnect()

    async def test_query_excludes_retracted(self) -> None:
        store = SQLiteOrgFactStore(":memory:")
        await store.connect()
        try:
            await store.save(_make_fact("f1", "Active fact"))
            await store.save(_make_fact("f2", "Retracted fact"))
            await store.delete("f2")
            results = await store.query(limit=10)
            ids = [f.id for f in results]
            assert "f1" in ids
            assert "f2" not in ids
        finally:
            await store.disconnect()

    async def test_list_by_category_excludes_retracted(self) -> None:
        store = SQLiteOrgFactStore(":memory:")
        await store.connect()
        try:
            await store.save(
                _make_fact("f1", category=OrgFactCategory.ADR),
            )
            await store.save(
                _make_fact("f2", category=OrgFactCategory.ADR),
            )
            await store.delete("f1")
            results = await store.list_by_category(OrgFactCategory.ADR)
            assert len(results) == 1
            assert results[0].id == "f2"
        finally:
            await store.disconnect()


@pytest.mark.unit
class TestMvccVersionCounter:
    """Version counter is per-fact and monotonic."""

    async def test_independent_fact_versions(self) -> None:
        store = SQLiteOrgFactStore(":memory:")
        await store.connect()
        try:
            await store.save(_make_fact("f1", "First fact"))
            await store.save(_make_fact("f2", "Second fact"))
            log_f1 = await store.get_operation_log("f1")
            log_f2 = await store.get_operation_log("f2")
            assert log_f1[0].version == 1
            assert log_f2[0].version == 1
        finally:
            await store.disconnect()

    async def test_version_increments_across_operations(self) -> None:
        store = SQLiteOrgFactStore(":memory:")
        await store.connect()
        try:
            await store.save(_make_fact("f1", "v1"))
            await store.save(_make_fact("f1", "v2"))
            await store.delete("f1")
            log = await store.get_operation_log("f1")
            assert [e.version for e in log] == [1, 2, 3]
        finally:
            await store.disconnect()


@pytest.mark.unit
class TestMvccSnapshotAt:
    """Time-travel queries via snapshot_at()."""

    async def test_snapshot_before_any_operations(self) -> None:
        store = SQLiteOrgFactStore(":memory:")
        await store.connect()
        try:
            past = datetime.now(UTC) - timedelta(hours=1)
            await store.save(_make_fact("f1"))
            snapshot = await store.snapshot_at(past)
            assert len(snapshot) == 0
        finally:
            await store.disconnect()

    async def test_snapshot_after_publish(self) -> None:
        store = SQLiteOrgFactStore(":memory:")
        await store.connect()
        try:
            await store.save(_make_fact("f1", "Published fact"))
            future = datetime.now(UTC) + timedelta(hours=1)
            snapshot = await store.snapshot_at(future)
            assert len(snapshot) == 1
            assert snapshot[0].fact_id == "f1"
            assert snapshot[0].content == "Published fact"
            assert snapshot[0].retracted_at is None
        finally:
            await store.disconnect()

    async def test_snapshot_after_retract(self) -> None:
        store = SQLiteOrgFactStore(":memory:")
        await store.connect()
        try:
            await store.save(_make_fact("f1"))
            await store.delete("f1")
            future = datetime.now(UTC) + timedelta(hours=1)
            snapshot = await store.snapshot_at(future)
            assert len(snapshot) == 1
            assert snapshot[0].fact_id == "f1"
            assert snapshot[0].retracted_at is not None
        finally:
            await store.disconnect()

    async def test_snapshot_between_publish_and_retract(self) -> None:
        """Snapshot at a time between publish and retract shows active fact."""
        store = SQLiteOrgFactStore(":memory:")
        await store.connect()
        try:
            await store.save(_make_fact("f1"))
            # Small delay to ensure distinct timestamps
            await asyncio.sleep(0.01)
            mid_ts = datetime.now(UTC)
            await asyncio.sleep(0.01)
            await store.delete("f1")
            snapshot = await store.snapshot_at(mid_ts)
            assert len(snapshot) == 1
            assert snapshot[0].retracted_at is None
        finally:
            await store.disconnect()

    async def test_snapshot_at_when_not_connected(self) -> None:
        store = SQLiteOrgFactStore(":memory:")
        with pytest.raises(OrgMemoryConnectionError):
            await store.snapshot_at(datetime.now(UTC))


@pytest.mark.unit
class TestMvccGetOperationLog:
    """Audit trail via get_operation_log()."""

    async def test_full_audit_trail(self) -> None:
        store = SQLiteOrgFactStore(":memory:")
        await store.connect()
        try:
            await store.save(_make_fact("f1", "Original"))
            await store.save(_make_fact("f1", "Updated"))
            await store.delete("f1")
            log = await store.get_operation_log("f1")
            assert len(log) == 3
            assert log[0].operation_type == "PUBLISH"
            assert log[0].content == "Original"
            assert log[1].operation_type == "PUBLISH"
            assert log[1].content == "Updated"
            assert log[2].operation_type == "RETRACT"
            assert log[2].content is None
            assert [e.version for e in log] == [1, 2, 3]
        finally:
            await store.disconnect()

    async def test_empty_log_for_unknown_fact(self) -> None:
        store = SQLiteOrgFactStore(":memory:")
        await store.connect()
        try:
            log = await store.get_operation_log("nonexistent")
            assert log == ()
        finally:
            await store.disconnect()

    async def test_log_when_not_connected(self) -> None:
        store = SQLiteOrgFactStore(":memory:")
        with pytest.raises(OrgMemoryConnectionError):
            await store.get_operation_log("f1")

    async def test_log_preserves_all_operations(self) -> None:
        """Even after retraction, all operations are preserved."""
        store = SQLiteOrgFactStore(":memory:")
        await store.connect()
        try:
            await store.save(
                _make_fact("f1", "v1", tags=("tag-a",)),
            )
            await store.save(
                _make_fact("f1", "v2", tags=("tag-b",)),
            )
            await store.delete("f1")
            log = await store.get_operation_log("f1")
            assert log[0].tags == ("tag-a",)
            assert log[1].tags == ("tag-b",)
            assert log[2].tags == ()
        finally:
            await store.disconnect()


@pytest.mark.unit
class TestMvccConcurrentPublishes:
    """Two agents publishing the same fact_id."""

    async def test_both_operations_in_log(self) -> None:
        store = SQLiteOrgFactStore(":memory:")
        await store.connect()
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
            await store.save(
                _make_fact("shared-fact", "Agent A version", author=agent_a),
            )
            await store.save(
                _make_fact("shared-fact", "Agent B version", author=agent_b),
            )
            log = await store.get_operation_log("shared-fact")
            assert len(log) == 2
            assert log[0].author_agent_id == "agent-a"
            assert log[1].author_agent_id == "agent-b"
            # Snapshot has last writer wins
            fact = await store.get("shared-fact")
            assert fact is not None
            assert fact.content == "Agent B version"
        finally:
            await store.disconnect()
