"""Fixtures for SQLite persistence unit tests."""

from pathlib import Path
from typing import TYPE_CHECKING

import aiosqlite
import pytest

from synthorg.persistence import atlas

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator


@pytest.fixture
async def memory_db() -> AsyncGenerator[aiosqlite.Connection]:
    """Raw in-memory SQLite connection (no migrations)."""
    db = await aiosqlite.connect(":memory:")
    try:
        db.row_factory = aiosqlite.Row
        yield db
    finally:
        await db.close()


@pytest.fixture
async def migrated_db(tmp_path: Path) -> AsyncGenerator[aiosqlite.Connection]:
    """Temp-file SQLite connection with Atlas migrations applied.

    Uses an isolated copy of the revisions directory so parallel
    xdist workers do not contend on the Atlas directory lock.
    """
    db_path = tmp_path / "test.db"
    rev_url = atlas.copy_revisions(tmp_path / "revisions")
    await atlas.migrate_apply(
        atlas.to_sqlite_url(str(db_path)),
        revisions_url=rev_url,
    )
    db = await aiosqlite.connect(str(db_path))
    try:
        db.row_factory = aiosqlite.Row
        yield db
    finally:
        await db.close()
