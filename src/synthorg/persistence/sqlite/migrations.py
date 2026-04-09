"""Schema migration via Atlas CLI.

All schema management is handled by Atlas declarative migrations.
The ``schema.sql`` file defines the desired state; Atlas generates
versioned migration SQL in ``revisions/``.  At startup, the
``SQLitePersistenceBackend.migrate()`` method invokes Atlas to
apply pending revisions.

Legacy helpers (``_add_column_if_missing``, ``_check_legacy_workflow_versions``)
have been removed -- Atlas tracks schema versions in its
``atlas_schema_revisions`` table.
"""
