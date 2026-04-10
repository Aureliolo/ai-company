"""Postgres persistence backend.

Production-grade ``PersistenceBackend`` implementation using psycopg 3
and ``psycopg_pool.AsyncConnectionPool``.  Stores JSON fields as
native ``JSONB`` and timestamps as ``TIMESTAMPTZ`` to expose
Postgres-native features (GIN indexes, timezone-aware comparisons)
while preserving the same protocol surface as the SQLite backend.
"""

from synthorg.persistence.postgres.backend import PostgresPersistenceBackend

__all__ = ["PostgresPersistenceBackend"]
