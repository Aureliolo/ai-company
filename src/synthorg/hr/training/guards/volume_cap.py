"""Volume cap guard for training mode.

Enforces hard per-content-type caps on the number of training items.
Items are already ranked by the curation stage, so truncation
preserves the highest-scoring items.
"""

from typing import TYPE_CHECKING

from synthorg.hr.training.models import (
    ContentType,
    TrainingGuardDecision,
    TrainingItem,
)
from synthorg.observability import get_logger
from synthorg.observability.events.training import (
    HR_TRAINING_VOLUME_CAP_ENFORCED,
)

if TYPE_CHECKING:
    from synthorg.hr.training.models import TrainingPlan

logger = get_logger(__name__)


class VolumeCapGuard:
    """Hard per-content-type volume cap guard.

    Truncates items to the cap specified in the training plan.
    If no cap is defined for a content type, all items pass.
    """

    @property
    def name(self) -> str:
        """Guard name."""
        return "volume_cap"

    async def evaluate(
        self,
        items: tuple[TrainingItem, ...],
        *,
        content_type: ContentType,
        plan: TrainingPlan,
    ) -> TrainingGuardDecision:
        """Apply volume cap for the content type.

        Args:
            items: Ranked items (highest score first).
            content_type: Content type being evaluated.
            plan: Training plan with volume caps.

        Returns:
            Decision with truncated items if over cap.
        """
        if not items:
            return TrainingGuardDecision(
                approved_items=(),
                rejected_count=0,
                guard_name="volume_cap",
            )

        # Find cap for this content type.
        cap = None
        for ct, limit in plan.volume_caps:
            if ct == content_type:
                cap = limit
                break

        if cap is None:
            # No cap defined -- pass all.
            return TrainingGuardDecision(
                approved_items=items,
                rejected_count=0,
                guard_name="volume_cap",
            )

        approved = items[:cap]
        rejected_count = max(0, len(items) - cap)

        if rejected_count > 0:
            logger.debug(
                HR_TRAINING_VOLUME_CAP_ENFORCED,
                content_type=content_type.value,
                cap=cap,
                input_count=len(items),
                rejected_count=rejected_count,
            )

        reasons = (
            (
                f"Exceeded {content_type.value} cap of {cap} "
                f"({rejected_count} items truncated)",
            )
            if rejected_count > 0
            else ()
        )

        return TrainingGuardDecision(
            approved_items=approved,
            rejected_count=rejected_count,
            guard_name="volume_cap",
            rejection_reasons=reasons,
        )
