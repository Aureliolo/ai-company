"""Workflow definition event name constants for observability.

Covers CRUD, validation, and export operations on visual
workflow definitions.
"""

from typing import Final

# -- CRUD events --------------------------------------------------------------

WORKFLOW_DEF_CREATED: Final[str] = "workflow.definition.created"
"""New workflow definition created."""

WORKFLOW_DEF_CREATE_CONFLICT: Final[str] = "workflow.definition.create_conflict"
"""Create rejected because an existing definition has the same id."""

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

# -- Subworkflow registry events ---------------------------------------------

SUBWORKFLOW_REGISTERED: Final[str] = "workflow.subworkflow.registered"
"""A new subworkflow version was published to the registry."""

SUBWORKFLOW_RESOLVED: Final[str] = "workflow.subworkflow.resolved"
"""A subworkflow reference was resolved against the registry."""

SUBWORKFLOW_DELETED: Final[str] = "workflow.subworkflow.deleted"
"""A subworkflow version was deleted from the registry."""

SUBWORKFLOW_NOT_FOUND: Final[str] = "workflow.subworkflow.not_found"
"""Lookup of a subworkflow coordinate (id / version / latest) returned no row.

Distinct from :data:`SUBWORKFLOW_INVALID_REQUEST` so callers can split
"missing resource" reads from "malformed caller input" without inspecting
a structured field.
"""

SUBWORKFLOW_PUBLISH_FAILED: Final[str] = "workflow.subworkflow.publish_failed"
"""``SubworkflowService.create`` failed before the service-level success log.

Carries ``subworkflow_id`` / ``version`` / ``saved_by`` plus the typed
exception so the audit trail records publish failures alongside the
``SUBWORKFLOW_REGISTERED`` success path.
"""

SUBWORKFLOW_DELETE_BLOCKED: Final[str] = "workflow.subworkflow.delete_blocked"
"""A subworkflow delete was rejected because parents still reference it.

Distinct from :data:`SUBWORKFLOW_DELETED` so audit-trail and deletion
metrics can separate successful removals from parent-cascade rejections
without inspecting structured fields.
"""

SUBWORKFLOW_CYCLE_DETECTED: Final[str] = "workflow.subworkflow.cycle_detected"
"""Static cycle detection rejected a subworkflow reference graph."""

SUBWORKFLOW_IO_INVALID: Final[str] = "workflow.subworkflow.io_invalid"
"""Save-time I/O validation rejected a subworkflow reference."""

SUBWORKFLOW_INVALID_REQUEST: Final[str] = "workflow.subworkflow.invalid_request"
"""API request to create or update a subworkflow was invalid."""
