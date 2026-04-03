"""Persistence error hierarchy.

All persistence-related errors inherit from ``PersistenceError`` so
callers can catch the entire family with a single except clause.
"""


class PersistenceError(Exception):
    """Base exception for all persistence operations."""


class PersistenceConnectionError(PersistenceError):
    """Raised when a backend connection cannot be established or is lost."""


class MigrationError(PersistenceError):
    """Raised when a database migration fails."""


class RecordNotFoundError(PersistenceError):
    """Raised when a requested record does not exist.

    Used by ``ArtifactStorageBackend.retrieve()`` when no content
    exists for the given artifact ID.  Repository ``get()`` methods
    return ``None`` on miss instead of raising.
    """


class DuplicateRecordError(PersistenceError):
    """Raised when inserting a record that already exists."""


class QueryError(PersistenceError):
    """Raised when a query fails due to invalid parameters or backend issues."""


class VersionConflictError(QueryError):
    """Raised when an optimistic concurrency version check fails."""


class ArtifactTooLargeError(PersistenceError):
    """Raised when a single artifact exceeds the maximum allowed size."""


class ArtifactStorageFullError(PersistenceError):
    """Raised when total artifact storage exceeds capacity."""
