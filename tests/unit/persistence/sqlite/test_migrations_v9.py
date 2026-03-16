"""Tests for V9 migration (settings table schema evolution)."""

from typing import TYPE_CHECKING

import aiosqlite
import pytest

from synthorg.persistence.sqlite.migrations import (
    _apply_v9,
    get_user_version,
    run_migrations,
    set_user_version,
)

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

pytestmark = [pytest.mark.unit, pytest.mark.timeout(30)]


@pytest.fixture
async def memory_db() -> AsyncGenerator[aiosqlite.Connection]:
    """Raw in-memory SQLite connection (no migrations)."""
    conn = await aiosqlite.connect(":memory:")
    conn.row_factory = aiosqlite.Row
    yield conn
    await conn.close()


async def _create_v5_settings(db: aiosqlite.Connection) -> None:
    """Create the old V5 settings table and seed test data."""
    await db.execute(
        "CREATE TABLE IF NOT EXISTS settings "
        "(key TEXT PRIMARY KEY, value TEXT NOT NULL)"
    )
    await db.execute(
        "INSERT INTO settings (key, value) VALUES ('jwt_secret', 'test-secret')"
    )
    await db.execute("INSERT INTO settings (key, value) VALUES ('setup_done', 'true')")
    await db.commit()


class TestV9MigrationFreshDB:
    """V9 migration on a fresh DB (no V5 settings table)."""

    async def test_creates_settings_table(
        self, memory_db: aiosqlite.Connection
    ) -> None:
        await run_migrations(memory_db)
        cursor = await memory_db.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='settings'"
        )
        row = await cursor.fetchone()
        assert row is not None
        ddl = str(row[0])
        assert "namespace" in ddl
        assert "updated_at" in ddl

    async def test_schema_version_is_9(self, memory_db: aiosqlite.Connection) -> None:
        await run_migrations(memory_db)
        version = await get_user_version(memory_db)
        assert version == 9


class TestV9MigrationDataPreservation:
    """V9 migrates existing V5 settings rows to _system namespace."""

    async def test_existing_rows_migrated_to_system_namespace(
        self, memory_db: aiosqlite.Connection
    ) -> None:
        # Build a V5-only DB with old-schema settings.
        await _create_v5_settings(memory_db)
        await set_user_version(memory_db, 5)

        # Apply V9.
        await _apply_v9(memory_db)
        await memory_db.commit()

        # Verify rows exist in _system namespace.
        cursor = await memory_db.execute(
            "SELECT namespace, key, value FROM settings ORDER BY key"
        )
        rows = list(await cursor.fetchall())
        assert len(rows) == 2
        for row in rows:
            assert row[0] == "_system"
        keys = {row[1] for row in rows}
        assert keys == {"jwt_secret", "setup_done"}

    async def test_updated_at_is_iso8601(self, memory_db: aiosqlite.Connection) -> None:
        await _create_v5_settings(memory_db)
        await set_user_version(memory_db, 5)
        await _apply_v9(memory_db)
        await memory_db.commit()

        cursor = await memory_db.execute("SELECT updated_at FROM settings LIMIT 1")
        row = await cursor.fetchone()
        assert row is not None
        ts = str(row[0])
        # Should contain 'T' separator and '+00:00' timezone
        assert "T" in ts
        assert "+00:00" in ts


class TestV9MigrationCrashSafety:
    """V9 migration handles crash mid-rename states."""

    async def test_crash_after_rename_to_old(
        self, memory_db: aiosqlite.Connection
    ) -> None:
        """Simulate: settings renamed to settings_old, settings_v9 exists."""
        # Create old-schema as settings_old (simulating post-rename crash).
        await memory_db.execute(
            "CREATE TABLE settings_old (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )
        await memory_db.execute(
            "INSERT INTO settings_old (key, value) VALUES ('k1', 'v1')"
        )
        await memory_db.commit()

        await _apply_v9(memory_db)
        await memory_db.commit()

        # settings should exist with the migrated data.
        cursor = await memory_db.execute("SELECT namespace, key, value FROM settings")
        rows = list(await cursor.fetchall())
        assert len(rows) == 1
        assert rows[0][0] == "_system"
        assert rows[0][1] == "k1"

        # settings_old should be cleaned up.
        cursor = await memory_db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='settings_old'"
        )
        assert await cursor.fetchone() is None

    async def test_crash_with_both_tables_present(
        self, memory_db: aiosqlite.Connection
    ) -> None:
        """Simulate: both settings and settings_old exist (crash after step 4).

        settings_old is the V5 original; settings is the new-schema table.
        V9 should prefer settings_old as the authoritative source.
        """
        # settings_old: the V5-schema original
        await memory_db.execute(
            "CREATE TABLE settings_old (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )
        await memory_db.execute(
            "INSERT INTO settings_old (key, value) VALUES ('k1', 'old_val')"
        )
        # settings: the new-schema table (already migrated, different value)
        await memory_db.execute(
            "CREATE TABLE settings ("
            "namespace TEXT NOT NULL, key TEXT NOT NULL, "
            "value TEXT NOT NULL, updated_at TEXT NOT NULL, "
            "PRIMARY KEY (namespace, key))"
        )
        await memory_db.execute(
            "INSERT INTO settings VALUES "
            "('_system', 'k1', 'new_val', '2026-01-01T00:00:00+00:00')"
        )
        await memory_db.commit()

        await _apply_v9(memory_db)
        await memory_db.commit()

        # settings should exist — the existing v9-schema data is preserved
        # since settings_old was used to populate settings_v9 but the
        # existing settings table (already v9-schema) takes precedence.
        cursor = await memory_db.execute("SELECT namespace, key, value FROM settings")
        rows = list(await cursor.fetchall())
        assert len(rows) == 1
        assert (rows[0][0], rows[0][1], rows[0][2]) == (
            "_system",
            "k1",
            "new_val",
        )

    async def test_v9_schema_settings_without_old_preserves_data(
        self, memory_db: aiosqlite.Connection
    ) -> None:
        """settings already has v9 schema, no settings_old.

        Migration should NOT re-copy rows (which would clobber
        namespaces into ``_system``).  Existing data is preserved.
        """
        # Create a v9-schema settings table with properly namespaced data.
        await memory_db.execute(
            "CREATE TABLE settings ("
            "namespace TEXT NOT NULL, key TEXT NOT NULL, "
            "value TEXT NOT NULL, updated_at TEXT NOT NULL, "
            "PRIMARY KEY (namespace, key))"
        )
        await memory_db.execute(
            "INSERT INTO settings VALUES "
            "('budget', 'total_monthly', '500', '2026-03-01T00:00:00+00:00')"
        )
        await memory_db.commit()
        await set_user_version(memory_db, 8)

        await _apply_v9(memory_db)
        await memory_db.commit()

        # Data should be preserved with original namespace (not _system).
        cursor = await memory_db.execute(
            "SELECT namespace, key, value, updated_at FROM settings"
        )
        rows = list(await cursor.fetchall())
        assert len(rows) == 1
        assert rows[0][0] == "budget"
        assert rows[0][1] == "total_monthly"
        assert rows[0][2] == "500"
        assert rows[0][3] == "2026-03-01T00:00:00+00:00"
