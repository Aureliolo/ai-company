"""Shared fixtures for ontology integration tests."""

from collections.abc import AsyncGenerator
from pathlib import Path

import pytest

from synthorg.ontology.backends.sqlite.backend import SQLiteOntologyBackend

pytestmark = pytest.mark.integration


@pytest.fixture
def db_path(tmp_path: Path) -> str:
    """Temporary on-disk database path."""
    return str(tmp_path / "ontology_test.db")


@pytest.fixture
async def on_disk_backend(
    db_path: str,
) -> AsyncGenerator[SQLiteOntologyBackend]:
    """A connected on-disk SQLiteOntologyBackend."""
    backend = SQLiteOntologyBackend(db_path=db_path)
    await backend.connect()
    yield backend
    await backend.disconnect()
