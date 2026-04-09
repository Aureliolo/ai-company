"""Ontology schema migration (deprecated).

Ontology tables are now consolidated into the persistence schema
and managed by Atlas declarative migrations.  See
``src/synthorg/persistence/sqlite/schema.sql`` for the canonical
schema and ``src/synthorg/persistence/sqlite/revisions/`` for
versioned migrations.
"""
