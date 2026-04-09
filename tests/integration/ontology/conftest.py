"""Shared fixtures for ontology integration tests."""

from collections.abc import AsyncGenerator
from pathlib import Path

import pytest

from synthorg.ontology.backends.sqlite.backend import SQLiteOntologyBackend
from synthorg.persistence import atlas

pytestmark = pytest.mark.integration


@pytest.fixture
async def db_path(tmp_path: Path) -> str:
    """Temporary on-disk database path with Atlas migrations applied."""
    path = str(tmp_path / "ontology_test.db")
    rev_url = atlas.copy_revisions(tmp_path / "revisions")
    await atlas.migrate_apply(
        atlas.to_sqlite_url(path),
        revisions_url=rev_url,
        skip_lock=True,
    )
    return path


@pytest.fixture
async def on_disk_backend(
    db_path: str,
) -> AsyncGenerator[SQLiteOntologyBackend]:
    """A connected on-disk SQLiteOntologyBackend."""
    backend = SQLiteOntologyBackend(db_path=db_path)
    await backend.connect()
    yield backend
    await backend.disconnect()
