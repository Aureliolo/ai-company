"""Negative tests for ``_build_*_store`` dispatchers in api.lifecycle.

The three dispatchers (session, lockout, refresh) pick the concrete
backend class by inspecting ``type(db).__name__``.  When an operator
plumbs in a new persistence backend, the dispatcher must raise a clear
``TypeError`` at startup rather than silently routing to the SQLite
implementation and producing cryptic ``AttributeError`` crashes when the
wrong driver receives the wrong handle.

Positive-path Postgres coverage lives in
``tests/integration/persistence/test_fresh_install_postgres_cli.py``.
"""

import pytest

from synthorg.api.auth.config import AuthConfig
from synthorg.api.lifecycle import (
    _build_lockout_store,
    _build_refresh_store,
    _build_session_store,
)

pytestmark = pytest.mark.unit


class TestBuildStoreDispatchRejectsUnknownHandle:
    """Each ``_build_*_store`` raises ``TypeError`` on unknown DB types."""

    def test_session_store_rejects_plain_object(self) -> None:
        with pytest.raises(
            TypeError,
            match="Unsupported session-store DB handle",
        ):
            _build_session_store(object())

    def test_lockout_store_rejects_plain_object(self) -> None:
        with pytest.raises(
            TypeError,
            match="Unsupported lockout-store DB handle",
        ):
            _build_lockout_store(object(), AuthConfig())

    def test_refresh_store_rejects_plain_object(self) -> None:
        with pytest.raises(
            TypeError,
            match="Unsupported refresh-store DB handle",
        ):
            _build_refresh_store(object())

    def test_session_store_rejects_string_handle(self) -> None:
        """A str handle should not coincidentally match 'Connection'."""
        with pytest.raises(TypeError):
            _build_session_store("not-a-handle")

    def test_lockout_store_rejects_dict_handle(self) -> None:
        with pytest.raises(TypeError):
            _build_lockout_store({}, AuthConfig())

    def test_refresh_store_rejects_int_handle(self) -> None:
        with pytest.raises(TypeError):
            _build_refresh_store(42)


class TestBuildStoreDispatchPositivePaths:
    """Dispatchers pick the correct concrete class for each backend.

    The SQLite classes accept a plain ``aiosqlite.Connection``; exercising
    them with a real in-memory connection covers the positive dispatch
    branch without an integration test.  Postgres positive paths are
    covered by ``test_fresh_install_postgres_cli.py`` with a real
    testcontainer pool.
    """

    async def test_session_store_builds_sqlite_variant(self) -> None:
        import aiosqlite

        from synthorg.api.auth.session_store import SqliteSessionStore

        conn = await aiosqlite.connect(":memory:")
        try:
            store = _build_session_store(conn)
        finally:
            await conn.close()
        assert isinstance(store, SqliteSessionStore)

    async def test_lockout_store_builds_sqlite_variant(self) -> None:
        import aiosqlite

        from synthorg.api.auth.lockout_store import SqliteLockoutStore

        conn = await aiosqlite.connect(":memory:")
        try:
            store = _build_lockout_store(conn, AuthConfig())
        finally:
            await conn.close()
        assert isinstance(store, SqliteLockoutStore)

    async def test_refresh_store_builds_sqlite_variant(self) -> None:
        import aiosqlite

        from synthorg.api.auth.refresh_store import SqliteRefreshStore

        conn = await aiosqlite.connect(":memory:")
        try:
            store = _build_refresh_store(conn)
        finally:
            await conn.close()
        assert isinstance(store, SqliteRefreshStore)
