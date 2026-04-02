"""Workflow definition event name constants for observability.

Covers CRUD, validation, and export operations on visual
workflow definitions.
"""

# -- CRUD events --------------------------------------------------------------

WORKFLOW_DEF_CREATED: str = "workflow.definition.created"
"""New workflow definition created."""

WORKFLOW_DEF_UPDATED: str = "workflow.definition.updated"
"""Existing workflow definition updated."""

WORKFLOW_DEF_DELETED: str = "workflow.definition.deleted"
"""Workflow definition deleted."""

WORKFLOW_DEF_FETCHED: str = "workflow.definition.fetched"
"""Workflow definition retrieved."""

WORKFLOW_DEF_LISTED: str = "workflow.definition.listed"
"""Workflow definitions listed."""

# -- Validation events --------------------------------------------------------

WORKFLOW_DEF_VALIDATED: str = "workflow.definition.validated"
"""Workflow definition validated successfully."""

WORKFLOW_DEF_VALIDATION_FAILED: str = "workflow.definition.validation_failed"
"""Workflow definition validation failed."""

# -- Export events ------------------------------------------------------------

WORKFLOW_DEF_EXPORTED: str = "workflow.definition.exported"
"""Workflow definition exported as YAML."""

WORKFLOW_DEF_EXPORT_FAILED: str = "workflow.definition.export_failed"
"""Workflow definition export failed."""
