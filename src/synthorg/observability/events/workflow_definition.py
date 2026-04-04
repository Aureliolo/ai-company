"""Workflow definition event name constants for observability.

Covers CRUD, validation, and export operations on visual
workflow definitions.
"""

from typing import Final

# -- CRUD events --------------------------------------------------------------

WORKFLOW_DEF_CREATED: Final[str] = "workflow.definition.created"
"""New workflow definition created."""

WORKFLOW_DEF_UPDATED: Final[str] = "workflow.definition.updated"
"""Existing workflow definition updated."""

WORKFLOW_DEF_DELETED: Final[str] = "workflow.definition.deleted"
"""Workflow definition deleted."""

WORKFLOW_DEF_FETCHED: Final[str] = "workflow.definition.fetched"
"""Workflow definition retrieved."""

WORKFLOW_DEF_LISTED: Final[str] = "workflow.definition.listed"
"""Workflow definitions listed."""

# -- Validation events --------------------------------------------------------

WORKFLOW_DEF_VALIDATED: Final[str] = "workflow.definition.validated"
"""Workflow definition validated successfully."""

WORKFLOW_DEF_VALIDATION_FAILED: Final[str] = "workflow.definition.validation_failed"
"""Workflow definition validation failed."""

WORKFLOW_DEF_INVALID_REQUEST: Final[str] = "workflow.definition.invalid_request"
"""Workflow definition request validation failed (bad input)."""

WORKFLOW_DEF_NOT_FOUND: Final[str] = "workflow.definition.not_found"
"""Workflow definition not found."""

WORKFLOW_DEF_VERSION_CONFLICT: Final[str] = "workflow.definition.version_conflict"
"""Workflow definition version conflict on update."""

# -- Export events ------------------------------------------------------------

WORKFLOW_DEF_EXPORTED: Final[str] = "workflow.definition.exported"
"""Workflow definition exported as YAML."""

WORKFLOW_DEF_EXPORT_FAILED: Final[str] = "workflow.definition.export_failed"
"""Workflow definition export failed."""

# -- Version events -----------------------------------------------------------

WORKFLOW_DEF_VERSION_LISTED: Final[str] = "workflow.definition.version.listed"
"""Workflow definition versions listed."""

WORKFLOW_DEF_VERSION_FETCHED: Final[str] = "workflow.definition.version.fetched"
"""Workflow definition version fetched."""

WORKFLOW_DEF_ROLLED_BACK: Final[str] = "workflow.definition.rolled_back"
"""Workflow definition rolled back to a previous version."""

WORKFLOW_DEF_DIFF_COMPUTED: Final[str] = "workflow.definition.diff_computed"
"""Diff computed between two workflow definition versions."""
