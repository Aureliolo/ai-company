"""Tests for ``PersistenceBackend`` capability factory methods.

Locks the contract of ``build_ontology_versioning()`` -- the
capability method introduced by ARC-1 that replaces the
``isinstance(persistence, PostgresPersistenceBackend)`` check in
``api/auto_wire.py``.  Both the SQLite and Postgres backends must
construct a versioning service with the expected surface (``save_version``,
``list_versions``, ...) when invoked on a connected backend.

Postgres coverage lives alongside the existing integration-level
persistence tests; here we exercise SQLite and verify the protocol
surface of the returned service so any signature drift in
``create_ontology_versioning`` surfaces in unit CI.
"""

import pytest

from synthorg.persistence.config import SQLiteConfig
from synthorg.persistence.sqlite.backend import SQLitePersistenceBackend
from synthorg.versioning.service import VersioningService

pytestmark = pytest.mark.unit


class TestBuildOntologyVersioning:
    """``build_ontology_versioning()`` returns a wired versioning service."""

    async def test_sqlite_returns_versioning_service(self) -> None:
        """SQLite backend produces a ``VersioningService`` bound to its db."""
        backend = SQLitePersistenceBackend(SQLiteConfig(path=":memory:"))
        await backend.connect()
        try:
            service = backend.build_ontology_versioning()
            assert isinstance(service, VersioningService)
            # The service must expose the methods ``OntologyService``
            # consumes -- any rename in the factory surfaces here.
            assert hasattr(service, "snapshot_if_changed")
            assert hasattr(service, "force_snapshot")
            assert hasattr(service, "get_latest")
        finally:
            await backend.disconnect()

    async def test_sqlite_factory_not_connected_raises(self) -> None:
        """Calling the factory without ``connect()`` first raises cleanly."""
        from synthorg.persistence.errors import PersistenceConnectionError

        backend = SQLitePersistenceBackend(SQLiteConfig(path=":memory:"))
        with pytest.raises(PersistenceConnectionError):
            backend.build_ontology_versioning()
