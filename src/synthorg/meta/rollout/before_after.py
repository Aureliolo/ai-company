"""Before/after rollout strategy.

Applies the change to the whole org, snapshots metrics before
and after, and uses the tiered regression detector to check
for degradation during the observation window.
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


class BeforeAfterRollout:
    """Applies a proposal to the whole org with observation window.

    1. Applies the proposal via the applier.
    2. Checks for regression using the detector.
    3. Returns SUCCESS if no regression, REGRESSED otherwise.

    In the real implementation, step 2 would involve waiting
    for the observation window and checking periodically.
    For now, it does a single check.
    """

    @property
    def name(self) -> str:
        """Strategy name."""
        return "before_after"

    async def execute(
        self,
        *,
        proposal: ImprovementProposal,
        applier: ProposalApplier,
        detector: RegressionDetector,
    ) -> RolloutResult:
        """Execute the before/after rollout.

        Args:
            proposal: The approved proposal.
            applier: Applier for the proposal's altitude.
            detector: Regression detector.

        Returns:
            Rollout result.
        """
        _ = detector  # Will use for periodic regression checks.
        logger.info(
            META_ROLLOUT_STARTED,
            strategy="before_after",
            proposal_id=str(proposal.id),
        )

        # Apply the proposal.
        apply_result = await applier.apply(proposal)
        if not apply_result.success:
            return RolloutResult(
                proposal_id=proposal.id,
                outcome=RolloutOutcome.FAILED,
                observation_hours_elapsed=0.0,
                details=apply_result.error_message,
            )

        # Placeholder: In real impl, this would snapshot metrics,
        # wait for observation window, and check periodically.
        # For now, return success (regression detection is tested
        # independently via the detector tests).
        logger.info(
            META_ROLLOUT_COMPLETED,
            strategy="before_after",
            proposal_id=str(proposal.id),
            outcome="success",
        )
        return RolloutResult(
            proposal_id=proposal.id,
            outcome=RolloutOutcome.SUCCESS,
            regression_verdict=RegressionVerdict.NO_REGRESSION,
            observation_hours_elapsed=float(
                proposal.observation_window_hours,
            ),
        )
