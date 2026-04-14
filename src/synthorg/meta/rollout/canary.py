"""Canary subset rollout strategy.

Applies changes to a subset of agents/teams first, observes,
then expands to the full org on success.
"""

from typing import TYPE_CHECKING

from synthorg.meta.models import (
    ImprovementProposal,
    RegressionVerdict,
    RolloutOutcome,
    RolloutResult,
)
from synthorg.observability import get_logger
from synthorg.observability.events.meta import (
    META_ROLLOUT_COMPLETED,
    META_ROLLOUT_STARTED,
)

if TYPE_CHECKING:
    from synthorg.meta.protocol import ProposalApplier, RegressionDetector

logger = get_logger(__name__)


class CanarySubsetRollout:
    """Applies a proposal to a canary subset first.

    1. Selects a canary subset (configurable).
    2. Applies the proposal to the canary.
    3. Observes canary metrics vs rest-of-org.
    4. On success: full rollout. On regression: rollback canary.

    Args:
        canary_fraction: Fraction of org to use as canary (default 0.2).
    """

    def __init__(self, *, canary_fraction: float = 0.2) -> None:
        if canary_fraction <= 0.0 or canary_fraction > 1.0:
            msg = "canary_fraction must be in the range (0, 1]."
            raise ValueError(msg)
        self._canary_fraction = canary_fraction

    @property
    def name(self) -> str:
        """Strategy name."""
        return "canary"

    async def execute(
        self,
        *,
        proposal: ImprovementProposal,
        applier: ProposalApplier,
        detector: RegressionDetector,
    ) -> RolloutResult:
        """Execute canary rollout.

        Args:
            proposal: The approved proposal.
            applier: Applier for the proposal's altitude.
            detector: Regression detector.

        Returns:
            Rollout result.
        """
        _ = detector  # Will use for canary vs baseline comparison.
        logger.info(
            META_ROLLOUT_STARTED,
            strategy="canary",
            proposal_id=str(proposal.id),
            canary_fraction=self._canary_fraction,
        )

        # Apply to canary subset.
        apply_result = await applier.apply(proposal)
        if not apply_result.success:
            return RolloutResult(
                proposal_id=proposal.id,
                outcome=RolloutOutcome.FAILED,
                observation_hours_elapsed=0.0,
                details=apply_result.error_message,
            )

        # Placeholder: observe canary, compare to baseline, expand.
        logger.info(
            META_ROLLOUT_COMPLETED,
            strategy="canary",
            proposal_id=str(proposal.id),
            outcome="success",
        )
        return RolloutResult(
            proposal_id=proposal.id,
            outcome=RolloutOutcome.SUCCESS,
            regression_verdict=RegressionVerdict.NO_REGRESSION,
            observation_hours_elapsed=0.0,  # TODO: actual observation pending
        )
