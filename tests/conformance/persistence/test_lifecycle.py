"""Parametrized lifecycle conformance tests.

These tests exercise the ``PersistenceBackend`` protocol methods that
do not require any repository to be ported (connect, disconnect,
health_check, migrate idempotency, backend_name, get_db).  Every
concrete backend under ``tests/conformance/persistence/conftest.py``
must pass these tests identically.
"""

import pytest

from synthorg.persistence.protocol import PersistenceBackend


@pytest.mark.integration
class TestBackendLifecycle:
    async def test_is_connected_after_fixture(
        self,
        backend: PersistenceBackend,
    ) -> None:
        assert backend.is_connected is True

    async def test_backend_name_is_non_blank(
        self,
        backend: PersistenceBackend,
    ) -> None:
        # Conformance suite intentionally stays backend-agnostic:
        # asserting a fixed set like {"sqlite", "postgres"} would
        # force every new backend to edit this shared test.  The
        # protocol only requires a non-blank name.
        assert backend.backend_name

    async def test_health_check_passes(
        self,
        backend: PersistenceBackend,
    ) -> None:
        assert await backend.health_check() is True

    async def test_get_db_returns_non_none(
        self,
        backend: PersistenceBackend,
    ) -> None:
        db = backend.get_db()
        assert db is not None

    async def test_migrate_is_idempotent(
        self,
        backend: PersistenceBackend,
    ) -> None:
        """Running migrate a second time is a no-op."""
        await backend.migrate()
        await backend.migrate()
        # If this returned without raising, migrations are idempotent.
        assert backend.is_connected is True

    async def test_implements_protocol(
        self,
        backend: PersistenceBackend,
    ) -> None:
        assert isinstance(backend, PersistenceBackend)
