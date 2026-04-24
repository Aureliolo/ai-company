"""Shared helpers for SQLite and Postgres repository implementations.

The leading underscore signals "internal to the persistence layer".
Helpers expose pure functions that the backend repos call to remove
serialisation / deserialisation / error-classification duplication;
backend-specific bits (SQL placeholder style, JSON wrappers, error
class predicates) stay in the backend repo modules and are passed
into the helpers as callables.

Conformance tests target these helpers directly without instantiating
a database backend.
"""
