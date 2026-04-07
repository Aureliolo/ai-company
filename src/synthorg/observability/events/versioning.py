"""Generic versioning event name constants for observability."""

from typing import Final

VERSION_SAVED: Final[str] = "persistence.version.saved"
"""Version snapshot persisted successfully."""

VERSION_SAVE_FAILED: Final[str] = "persistence.version.save_failed"
"""Failed to persist version snapshot."""

VERSION_FETCH_FAILED: Final[str] = "persistence.version.fetch_failed"
"""Failed to retrieve version snapshot."""

VERSION_LISTED: Final[str] = "persistence.version.listed"
"""Version snapshots listed."""

VERSION_LIST_FAILED: Final[str] = "persistence.version.list_failed"
"""Failed to list version snapshots."""

VERSION_COUNT_FAILED: Final[str] = "persistence.version.count_failed"
"""Failed to count version snapshots."""

VERSION_DELETED: Final[str] = "persistence.version.deleted"
"""Version snapshots deleted for an entity."""

VERSION_DELETE_FAILED: Final[str] = "persistence.version.delete_failed"
"""Failed to delete version snapshots."""

VERSION_SNAPSHOT_SKIPPED: Final[str] = "persistence.version.snapshot_skipped"
"""Snapshot skipped -- content hash unchanged since last version."""

VERSION_SNAPSHOT_FAILED: Final[str] = "persistence.version.snapshot_failed"
"""Failed to create a version snapshot."""
