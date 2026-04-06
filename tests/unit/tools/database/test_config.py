"""Unit tests for database configuration models."""

import pytest

from synthorg.tools.database.config import DatabaseConfig, DatabaseConnectionConfig

_TEST_DB = "/tmp/test.db"  # noqa: S108
_TEST_DB_SHORT = "/tmp/t.db"  # noqa: S108
_MAIN_DB = "/tmp/main.db"  # noqa: S108


class TestDatabaseConnectionConfig:
    """Tests for DatabaseConnectionConfig."""

    @pytest.mark.unit
    def test_defaults(self) -> None:
        cfg = DatabaseConnectionConfig(database_path=_TEST_DB)
        assert cfg.query_timeout == 30.0
        assert cfg.read_only is True

    @pytest.mark.unit
    def test_frozen(self) -> None:
        cfg = DatabaseConnectionConfig(database_path=_TEST_DB)
        with pytest.raises(Exception):  # noqa: B017, PT011
            cfg.read_only = False  # type: ignore[misc]

    @pytest.mark.unit
    def test_timeout_bounds(self) -> None:
        DatabaseConnectionConfig(database_path=_TEST_DB_SHORT, query_timeout=0.1)
        with pytest.raises(Exception):  # noqa: B017, PT011
            DatabaseConnectionConfig(database_path=_TEST_DB_SHORT, query_timeout=0)
        with pytest.raises(Exception):  # noqa: B017, PT011
            DatabaseConnectionConfig(database_path=_TEST_DB_SHORT, query_timeout=301)


class TestDatabaseConfig:
    """Tests for DatabaseConfig."""

    @pytest.mark.unit
    def test_defaults(self) -> None:
        cfg = DatabaseConfig()
        assert cfg.connections == {}
        assert cfg.default_connection == "default"

    @pytest.mark.unit
    def test_with_connections(self) -> None:
        cfg = DatabaseConfig(
            connections={
                "main": DatabaseConnectionConfig(database_path=_MAIN_DB),
            },
            default_connection="main",
        )
        assert "main" in cfg.connections
        assert cfg.connections["main"].read_only is True
