"""Workflow version persistence event name constants for observability."""

from typing import Final

WORKFLOW_VERSION_SAVED: Final[str] = "persistence.workflow_version.saved"
"""Version snapshot persisted."""

WORKFLOW_VERSION_SAVE_FAILED: Final[str] = "persistence.workflow_version.save_failed"
"""Failed to persist version snapshot."""

WORKFLOW_VERSION_FETCH_FAILED: Final[str] = "persistence.workflow_version.fetch_failed"
"""Failed to retrieve version snapshot."""

WORKFLOW_VERSION_LISTED: Final[str] = "persistence.workflow_version.listed"
"""Version snapshots listed."""

WORKFLOW_VERSION_LIST_FAILED: Final[str] = "persistence.workflow_version.list_failed"
"""Failed to list version snapshots."""

WORKFLOW_VERSION_COUNT_FAILED: Final[str] = "persistence.workflow_version.count_failed"
"""Failed to count version snapshots."""

WORKFLOW_VERSION_DELETED: Final[str] = "persistence.workflow_version.deleted"
"""Version snapshots deleted for a definition."""

WORKFLOW_VERSION_DELETE_FAILED: Final[str] = (
    "persistence.workflow_version.delete_failed"
)
"""Failed to delete version snapshots."""

WORKFLOW_VERSION_SNAPSHOT_FAILED: Final[str] = (
    "persistence.workflow_version.snapshot_failed"
)
"""Supplementary version snapshot failed after successful definition save."""

WORKFLOW_VERSION_INVALID_REQUEST: Final[str] = (
    "persistence.workflow_version.invalid_request"
)
"""Caller passed an out-of-range pagination or revision argument."""
