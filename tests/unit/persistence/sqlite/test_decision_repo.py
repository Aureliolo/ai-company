"""Tests for SQLiteDecisionRepository."""

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from synthorg.core.enums import DecisionOutcome
from synthorg.engine.decisions import DecisionRecord
from synthorg.persistence.errors import DuplicateRecordError, QueryError
from synthorg.persistence.repositories import DecisionRepository
from synthorg.persistence.sqlite.decision_repo import SQLiteDecisionRepository

if TYPE_CHECKING:
    import aiosqlite


def _make_record(  # noqa: PLR0913
    *,
    record_id: str | None = None,
    task_id: str = "task-1",
    approval_id: str | None = None,
    executing_agent_id: str = "alice",
    reviewer_agent_id: str = "bob",
    decision: DecisionOutcome = DecisionOutcome.APPROVED,
    reason: str | None = None,
    criteria_snapshot: tuple[str, ...] = (),
    recorded_at: datetime | None = None,
    version: int = 1,
    metadata: dict[str, object] | None = None,
) -> DecisionRecord:
    return DecisionRecord(
        id=record_id or str(uuid4()),
        task_id=task_id,
        approval_id=approval_id,
        executing_agent_id=executing_agent_id,
        reviewer_agent_id=reviewer_agent_id,
        decision=decision,
        reason=reason,
        criteria_snapshot=criteria_snapshot,
        recorded_at=recorded_at or datetime.now(UTC),
        version=version,
        metadata=metadata if metadata is not None else {},
    )


@pytest.mark.unit
class TestSQLiteDecisionRepositoryAppendAndGet:
    async def test_append_and_get(self, migrated_db: aiosqlite.Connection) -> None:
        """Append a record, retrieve by ID, fields match."""
        repo = SQLiteDecisionRepository(migrated_db)
        record = _make_record(
            record_id="dr-001",
            criteria_snapshot=("JWT login", "Refresh works"),
            metadata={"sprint": "5"},
            reason="Code quality is high",
        )
        await repo.append(record)

        fetched = await repo.get("dr-001")
        assert fetched is not None
        assert fetched.id == "dr-001"
        assert fetched.task_id == "task-1"
        assert fetched.executing_agent_id == "alice"
        assert fetched.reviewer_agent_id == "bob"
        assert fetched.decision is DecisionOutcome.APPROVED
        assert fetched.reason == "Code quality is high"
        assert fetched.criteria_snapshot == ("JWT login", "Refresh works")
        assert fetched.metadata == {"sprint": "5"}
        assert fetched.version == 1

    async def test_get_missing_returns_none(
        self, migrated_db: aiosqlite.Connection
    ) -> None:
        """get returns None for unknown ID."""
        repo = SQLiteDecisionRepository(migrated_db)
        assert await repo.get("nonexistent") is None

    async def test_append_duplicate_id_raises(
        self, migrated_db: aiosqlite.Connection
    ) -> None:
        """Appending with an existing ID raises DuplicateRecordError."""
        repo = SQLiteDecisionRepository(migrated_db)
        record = _make_record(record_id="dr-dup")
        await repo.append(record)
        with pytest.raises(DuplicateRecordError):
            await repo.append(_make_record(record_id="dr-dup", task_id="task-2"))

    async def test_append_duplicate_task_version_raises(
        self, migrated_db: aiosqlite.Connection
    ) -> None:
        """Two records with same (task_id, version) raise DuplicateRecordError."""
        repo = SQLiteDecisionRepository(migrated_db)
        r1 = _make_record(record_id="dr-a", task_id="task-1", version=1)
        r2 = _make_record(record_id="dr-b", task_id="task-1", version=1)
        await repo.append(r1)
        with pytest.raises(DuplicateRecordError):
            await repo.append(r2)


@pytest.mark.unit
class TestSQLiteDecisionRepositoryListByTask:
    async def test_list_by_task_returns_version_asc(
        self, migrated_db: aiosqlite.Connection
    ) -> None:
        """list_by_task returns records ordered by version ascending."""
        repo = SQLiteDecisionRepository(migrated_db)
        await repo.append(_make_record(record_id="dr-1", task_id="task-A", version=2))
        await repo.append(_make_record(record_id="dr-2", task_id="task-A", version=1))
        await repo.append(_make_record(record_id="dr-3", task_id="task-A", version=3))
        await repo.append(_make_record(record_id="dr-4", task_id="task-B", version=1))

        results = await repo.list_by_task("task-A")
        assert len(results) == 3
        assert [r.version for r in results] == [1, 2, 3]

    async def test_list_by_task_empty(self, migrated_db: aiosqlite.Connection) -> None:
        """list_by_task returns empty tuple for unknown task."""
        repo = SQLiteDecisionRepository(migrated_db)
        assert await repo.list_by_task("task-nope") == ()


@pytest.mark.unit
class TestSQLiteDecisionRepositoryListByAgent:
    async def test_list_by_agent_as_executor(
        self, migrated_db: aiosqlite.Connection
    ) -> None:
        """list_by_agent with role='executor' filters by executing_agent_id."""
        repo = SQLiteDecisionRepository(migrated_db)
        now = datetime.now(UTC)
        await repo.append(
            _make_record(
                record_id="dr-1",
                executing_agent_id="alice",
                reviewer_agent_id="bob",
                recorded_at=now,
            )
        )
        await repo.append(
            _make_record(
                record_id="dr-2",
                task_id="task-2",
                executing_agent_id="carol",
                reviewer_agent_id="alice",
                recorded_at=now + timedelta(seconds=1),
            )
        )
        results = await repo.list_by_agent("alice", role="executor")
        assert len(results) == 1
        assert results[0].id == "dr-1"

    async def test_list_by_agent_as_reviewer(
        self, migrated_db: aiosqlite.Connection
    ) -> None:
        """list_by_agent with role='reviewer' filters by reviewer_agent_id."""
        repo = SQLiteDecisionRepository(migrated_db)
        now = datetime.now(UTC)
        await repo.append(
            _make_record(
                record_id="dr-1",
                executing_agent_id="alice",
                reviewer_agent_id="bob",
                recorded_at=now,
            )
        )
        await repo.append(
            _make_record(
                record_id="dr-2",
                task_id="task-2",
                executing_agent_id="carol",
                reviewer_agent_id="bob",
                recorded_at=now + timedelta(seconds=1),
            )
        )
        results = await repo.list_by_agent("bob", role="reviewer")
        assert len(results) == 2
        # DESC by recorded_at
        assert results[0].id == "dr-2"
        assert results[1].id == "dr-1"

    async def test_list_by_agent_invalid_role_raises(
        self, migrated_db: aiosqlite.Connection
    ) -> None:
        """Invalid role raises ValueError."""
        repo = SQLiteDecisionRepository(migrated_db)
        with pytest.raises(ValueError, match="role must be"):
            await repo.list_by_agent("alice", role="observer")


@pytest.mark.unit
class TestSQLiteDecisionRepositoryProtocol:
    def test_satisfies_protocol(self, migrated_db: aiosqlite.Connection) -> None:
        """SQLiteDecisionRepository is a DecisionRepository."""
        repo = SQLiteDecisionRepository(migrated_db)
        assert isinstance(repo, DecisionRepository)


@pytest.mark.unit
class TestSQLiteDecisionRepositorySerialization:
    async def test_criteria_and_metadata_round_trip(
        self, migrated_db: aiosqlite.Connection
    ) -> None:
        """criteria_snapshot and metadata survive JSON round-trip."""
        repo = SQLiteDecisionRepository(migrated_db)
        record = _make_record(
            record_id="dr-1",
            criteria_snapshot=("a", "b", "c"),
            metadata={"key": "value", "nested": {"x": 1}},
        )
        await repo.append(record)
        fetched = await repo.get("dr-1")
        assert fetched is not None
        assert fetched.criteria_snapshot == ("a", "b", "c")
        assert fetched.metadata == {"key": "value", "nested": {"x": 1}}

    async def test_corrupted_row_raises_query_error(
        self, migrated_db: aiosqlite.Connection
    ) -> None:
        """Corrupted criteria_snapshot JSON raises QueryError on read."""
        repo = SQLiteDecisionRepository(migrated_db)
        record = _make_record(record_id="dr-1")
        await repo.append(record)
        await migrated_db.execute(
            "UPDATE decision_records SET criteria_snapshot = ? WHERE id = ?",
            ("{not-valid-json}", "dr-1"),
        )
        await migrated_db.commit()
        with pytest.raises(QueryError):
            await repo.get("dr-1")
