"""Tests for SQLite schema migrations."""

import sqlite3
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

import pytest

from synthorg.persistence.errors import MigrationError
from synthorg.persistence.sqlite.migrations import (
    SCHEMA_VERSION,
    get_user_version,
    run_migrations,
    set_user_version,
)

if TYPE_CHECKING:
    import aiosqlite


@pytest.mark.unit
class TestUserVersion:
    async def test_default_version_is_zero(
        self, memory_db: aiosqlite.Connection
    ) -> None:
        assert await get_user_version(memory_db) == 0

    async def test_set_and_get_version(self, memory_db: aiosqlite.Connection) -> None:
        await set_user_version(memory_db, 42)
        assert await get_user_version(memory_db) == 42

    async def test_set_negative_version_raises(
        self, memory_db: aiosqlite.Connection
    ) -> None:
        with pytest.raises(MigrationError, match="non-negative integer"):
            await set_user_version(memory_db, -1)

    async def test_set_non_int_version_raises(
        self, memory_db: aiosqlite.Connection
    ) -> None:
        with pytest.raises(MigrationError, match="non-negative integer"):
            await set_user_version(memory_db, 2.5)  # type: ignore[arg-type]


@pytest.mark.unit
class TestRunMigrations:
    async def test_creates_tables(self, memory_db: aiosqlite.Connection) -> None:
        await run_migrations(memory_db)

        cursor = await memory_db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = [row[0] for row in await cursor.fetchall()]
        assert "tasks" in tables
        assert "cost_records" in tables
        assert "messages" in tables

    async def test_sets_version(self, memory_db: aiosqlite.Connection) -> None:
        await run_migrations(memory_db)
        assert await get_user_version(memory_db) == SCHEMA_VERSION

    async def test_idempotent(self, memory_db: aiosqlite.Connection) -> None:
        await run_migrations(memory_db)
        await run_migrations(memory_db)
        assert await get_user_version(memory_db) == SCHEMA_VERSION

    async def test_creates_indexes(self, memory_db: aiosqlite.Connection) -> None:
        await run_migrations(memory_db)

        cursor = await memory_db.execute(
            "SELECT name FROM sqlite_master WHERE type='index' "
            "AND name LIKE 'idx_%' ORDER BY name"
        )
        indexes = {row[0] for row in await cursor.fetchall()}
        expected = {
            "idx_tasks_status",
            "idx_tasks_assigned_to",
            "idx_tasks_project",
            "idx_cost_records_agent_id",
            "idx_cost_records_task_id",
            "idx_messages_channel",
            "idx_messages_timestamp",
        }
        assert expected.issubset(indexes)

    async def test_skips_when_already_at_version(
        self, migrated_db: aiosqlite.Connection
    ) -> None:
        """Running migrations on an already-migrated db is a no-op."""
        version_before = await get_user_version(migrated_db)
        await run_migrations(migrated_db)
        assert await get_user_version(migrated_db) == version_before

    async def test_v3_creates_parked_contexts_table(
        self, memory_db: aiosqlite.Connection
    ) -> None:
        await run_migrations(memory_db)
        cursor = await memory_db.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name='parked_contexts'"
        )
        row = await cursor.fetchone()
        assert row is not None

    async def test_v3_creates_parked_context_indexes(
        self, memory_db: aiosqlite.Connection
    ) -> None:
        await run_migrations(memory_db)
        cursor = await memory_db.execute(
            "SELECT name FROM sqlite_master WHERE type='index' "
            "AND name LIKE 'idx_pc_%' ORDER BY name"
        )
        indexes = {row[0] for row in await cursor.fetchall()}
        assert "idx_pc_agent_id" in indexes
        assert "idx_pc_approval_id" in indexes

    async def test_v4_creates_audit_entries_table(
        self, memory_db: aiosqlite.Connection
    ) -> None:
        """V4 migration creates the audit_entries table."""
        await run_migrations(memory_db)
        cursor = await memory_db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='audit_entries'"
        )
        row = await cursor.fetchone()
        assert row is not None

    async def test_v4_creates_audit_entry_indexes(
        self, memory_db: aiosqlite.Connection
    ) -> None:
        """All v4 indexes are present after migration."""
        await run_migrations(memory_db)
        cursor = await memory_db.execute(
            "SELECT name FROM sqlite_master WHERE type='index' "
            "AND name LIKE 'idx_ae_%' ORDER BY name"
        )
        indexes = {row[0] for row in await cursor.fetchall()}
        expected = {
            "idx_ae_timestamp",
            "idx_ae_agent_id",
            "idx_ae_action_type",
            "idx_ae_verdict",
            "idx_ae_risk_level",
        }
        assert expected.issubset(indexes)

    @pytest.mark.parametrize(
        "table_name",
        ["users", "api_keys", "settings"],
    )
    async def test_v5_creates_table(
        self,
        memory_db: aiosqlite.Connection,
        table_name: str,
    ) -> None:
        """V5 migration creates the expected tables."""
        await run_migrations(memory_db)
        cursor = await memory_db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,),
        )
        row = await cursor.fetchone()
        assert row is not None

    async def test_v5_creates_user_indexes(
        self, memory_db: aiosqlite.Connection
    ) -> None:
        await run_migrations(memory_db)
        cursor = await memory_db.execute(
            "SELECT name FROM sqlite_master WHERE type='index' "
            "AND name LIKE 'idx_%' AND name LIKE '%user%' ORDER BY name"
        )
        indexes = {row[0] for row in await cursor.fetchall()}
        assert "idx_api_keys_user_id" in indexes

    async def test_v8_creates_agent_states_table(
        self, memory_db: aiosqlite.Connection
    ) -> None:
        """V8 migration creates the agent_states table."""
        await run_migrations(memory_db)
        cursor = await memory_db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='agent_states'"
        )
        row = await cursor.fetchone()
        assert row is not None

    async def test_v8_creates_agent_states_columns(
        self, memory_db: aiosqlite.Connection
    ) -> None:
        """V8 migration creates the agent_states table with correct columns."""
        await run_migrations(memory_db)
        cursor = await memory_db.execute("PRAGMA table_info('agent_states')")
        columns = {row[1] for row in await cursor.fetchall()}
        expected = {
            "agent_id",
            "execution_id",
            "task_id",
            "status",
            "turn_count",
            "accumulated_cost_usd",
            "last_activity_at",
            "started_at",
        }
        assert columns == expected

    async def test_v8_agent_states_ddl_has_check_constraints(
        self, memory_db: aiosqlite.Connection
    ) -> None:
        """V8 DDL includes CHECK constraints for status, counters, and invariant."""
        await run_migrations(memory_db)
        cursor = await memory_db.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='agent_states'"
        )
        row = await cursor.fetchone()
        assert row is not None
        ddl = row[0]
        assert "CHECK (status IN ('idle', 'executing', 'paused'))" in ddl
        assert "CHECK (turn_count >= 0)" in ddl
        assert "CHECK (accumulated_cost_usd >= 0.0)" in ddl
        # Cross-field invariant CHECK
        assert "status = 'idle'" in ddl
        assert "execution_id IS NULL" in ddl
        assert "started_at IS NOT NULL" in ddl

    async def test_v8_check_constraint_rejects_invalid_status(
        self, memory_db: aiosqlite.Connection
    ) -> None:
        """CHECK constraint rejects rows with invalid status values."""
        await run_migrations(memory_db)
        with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
            await memory_db.execute(
                "INSERT INTO agent_states "
                "(agent_id, status, last_activity_at) "
                "VALUES (?, ?, ?)",
                ("a", "invalid", "2026-01-01T00:00:00+00:00"),
            )

    async def test_v8_creates_agent_states_composite_index(
        self, memory_db: aiosqlite.Connection
    ) -> None:
        """V8 migration creates the composite status+activity index."""
        await run_migrations(memory_db)
        cursor = await memory_db.execute(
            "SELECT name FROM sqlite_master WHERE type='index' "
            "AND name = 'idx_as_status_activity'"
        )
        row = await cursor.fetchone()
        assert row is not None

    async def test_v8_composite_index_covers_status_and_activity(
        self, memory_db: aiosqlite.Connection
    ) -> None:
        """Composite index covers (status, last_activity_at DESC)."""
        await run_migrations(memory_db)
        cursor = await memory_db.execute("PRAGMA index_xinfo('idx_as_status_activity')")
        rows = await cursor.fetchall()
        # index_xinfo columns: seqno, cid, name, desc, coll, key
        indexed = [(row[2], row[3]) for row in rows if row[5]]
        assert ("status", 0) in indexed  # status ASC
        assert ("last_activity_at", 1) in indexed  # last_activity_at DESC

    async def test_migration_failure_raises_migration_error(
        self, memory_db: aiosqlite.Connection
    ) -> None:
        """A failing migration step wraps the error as MigrationError."""
        failing_fn = AsyncMock(
            side_effect=sqlite3.OperationalError("simulated migration failure")
        )
        with (
            patch(
                "synthorg.persistence.sqlite.migrations._MIGRATIONS",
                [(1, failing_fn)],
            ),
            pytest.raises(MigrationError, match="Migration to version"),
        ):
            await run_migrations(memory_db)
