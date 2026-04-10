"""ReviewGateGuard -- routes adaptations through human approval for critical axes."""

from synthorg.engine.evolution.models import (
    AdaptationAxis,
    AdaptationDecision,
    AdaptationProposal,
)
from synthorg.observability import get_logger

logger = get_logger(__name__)


class ReviewGateGuard:
    """Routes critical adaptations through human approval.

    For specified adaptation axes (typically IDENTITY), rejects proposals
    with an indication that human review is required. Other axes are
    auto-approved.
    """

    def __init__(
        self,
        require_review_for: tuple[AdaptationAxis, ...] = (AdaptationAxis.IDENTITY,),
    ) -> None:
        """Initialize ReviewGateGuard.

        Args:
            require_review_for: Tuple of axes that require human review.
        """
        self._require_review_for = require_review_for

    @property
    def name(self) -> str:
        """Return guard name."""
        return "ReviewGateGuard"

    async def evaluate(
        self,
        proposal: AdaptationProposal,
    ) -> AdaptationDecision:
        """Evaluate whether a proposal requires human review.

        Args:
            proposal: The adaptation proposal to evaluate.

        Returns:
            Rejection if review is required, approval otherwise.
        """
        if proposal.axis in self._require_review_for:
            return AdaptationDecision(
                proposal_id=proposal.id,
                approved=False,
                guard_name=self.name,
                reason=f"Requires human approval for {proposal.axis.value} adaptations",
            )

        return AdaptationDecision(
            proposal_id=proposal.id,
            approved=True,
            guard_name=self.name,
            reason=f"Auto-approved for {proposal.axis.value} axis",
        )
