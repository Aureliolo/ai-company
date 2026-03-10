"""Promotion event constants for structured logging.

Constants follow the ``promotion.<subject>.<action>`` naming convention
and are passed as the first argument to structured log calls.
"""

from typing import Final

PROMOTION_EVALUATE_START: Final[str] = "promotion.evaluate.start"
PROMOTION_EVALUATE_COMPLETE: Final[str] = "promotion.evaluate.complete"
PROMOTION_REQUESTED: Final[str] = "promotion.requested"
PROMOTION_APPROVED: Final[str] = "promotion.approved"
PROMOTION_REJECTED: Final[str] = "promotion.rejected"
PROMOTION_APPLIED: Final[str] = "promotion.applied"
PROMOTION_COOLDOWN_ACTIVE: Final[str] = "promotion.cooldown.active"
DEMOTION_EVALUATE_START: Final[str] = "demotion.evaluate.start"
DEMOTION_APPLIED: Final[str] = "demotion.applied"
PROMOTION_MODEL_CHANGED: Final[str] = "promotion.model.changed"
