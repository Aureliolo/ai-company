"""Shared fixtures for database tool tests."""

from pathlib import Path

import pytest

from synthorg.tools.database.config import DatabaseConnectionConfig


@pytest.fixture
def read_only_config(tmp_path: Path) -> DatabaseConnectionConfig:
    """Read-only database config pointing to a temp file."""
    db_path = tmp_path / "test.db"
    return DatabaseConnectionConfig(
        database_path=str(db_path),
        read_only=True,
    )


@pytest.fixture
def writable_config(tmp_path: Path) -> DatabaseConnectionConfig:
    """Writable database config pointing to a temp file."""
    db_path = tmp_path / "test_write.db"
    return DatabaseConnectionConfig(
        database_path=str(db_path),
        read_only=False,
    )
