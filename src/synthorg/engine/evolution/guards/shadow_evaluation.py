"""ShadowEvaluationGuard -- placeholder for shadow execution (not yet implemented)."""

from synthorg.engine.evolution.models import AdaptationDecision, AdaptationProposal
from synthorg.observability import get_logger

logger = get_logger(__name__)


class ShadowEvaluationGuard:
    """Stub placeholder for shadow evaluation.

    Full shadow execution (running the adapted agent on test tasks before
    committing the change) is expensive and deferred. This guard always
    approves with a warning that shadow evaluation is not yet implemented.
    """

    @property
    def name(self) -> str:
        """Return guard name."""
        return "ShadowEvaluationGuard"

    async def evaluate(
        self,
        proposal: AdaptationProposal,
    ) -> AdaptationDecision:
        """Evaluate the proposal (placeholder implementation).

        Always approves. Full shadow execution is deferred.

        Args:
            proposal: The adaptation proposal to evaluate.

        Returns:
            Always approves with a placeholder reason.
        """
        return AdaptationDecision(
            proposal_id=proposal.id,
            approved=True,
            guard_name=self.name,
            reason="Shadow evaluation not yet implemented; auto-approved",
        )
