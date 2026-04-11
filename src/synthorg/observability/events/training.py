"""Training mode event constants for structured logging.

Constants follow the ``hr.training.<action>`` naming convention
and are passed as the first argument to structured log calls.
"""

from typing import Final

# -- Plan lifecycle ---------------------------------------------------

HR_TRAINING_PLAN_CREATED: Final[str] = "hr.training.plan_created"
HR_TRAINING_PLAN_EXECUTED: Final[str] = "hr.training.plan_executed"
HR_TRAINING_PLAN_IDEMPOTENT: Final[str] = "hr.training.plan_idempotent"
HR_TRAINING_SKIPPED: Final[str] = "hr.training.skipped"

# -- Extraction -------------------------------------------------------

HR_TRAINING_EXTRACTION_STARTED: Final[str] = "hr.training.extraction_started"
HR_TRAINING_ITEMS_EXTRACTED: Final[str] = "hr.training.items_extracted"

# -- Curation ---------------------------------------------------------

HR_TRAINING_CURATION_COMPLETE: Final[str] = "hr.training.curation_complete"

# -- Guards -----------------------------------------------------------

HR_TRAINING_GUARD_EVALUATION: Final[str] = "hr.training.guard_evaluation"
HR_TRAINING_SANITIZATION_APPLIED: Final[str] = "hr.training.sanitization_applied"
HR_TRAINING_VOLUME_CAP_ENFORCED: Final[str] = "hr.training.volume_cap_enforced"
HR_TRAINING_REVIEW_GATE_CREATED: Final[str] = "hr.training.review_gate_created"

# -- Error paths ------------------------------------------------------

HR_TRAINING_STORE_FAILED: Final[str] = "hr.training.store_failed"
