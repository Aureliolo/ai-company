"""Conformance tests.

Tests in this package run the *same* assertions against every
implementation of a given protocol.  The primary user is the
persistence layer: ``tests/conformance/persistence/`` exercises the
``PersistenceBackend`` protocol against both the SQLite and Postgres
concrete backends.

Tests here must not depend on backend-specific behavior (WAL mode,
JSONB operators, etc.).  Backend-specific coverage lives under
``tests/unit/persistence/sqlite/`` or
``tests/unit/persistence/postgres/``.
"""
