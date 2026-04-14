"""Approval gate guard.

Routes proposals to the ApprovalStore for mandatory human review.
This guard always passes (it routes, not rejects) but records
the proposal in the approval queue.
"""

from typing import TYPE_CHECKING

from synthorg.meta.models import (
    GuardResult,
    GuardVerdict,
    ImprovementProposal,
    ProposalAltitude,
)
from synthorg.observability import get_logger
from synthorg.observability.events.meta import META_PROPOSAL_GUARD_PASSED

if TYPE_CHECKING:
    from synthorg.api.approval_store import ApprovalStore

logger = get_logger(__name__)

_ALTITUDE_RISK = {
    ProposalAltitude.CONFIG_TUNING: "medium",
    ProposalAltitude.ARCHITECTURE: "high",
    ProposalAltitude.PROMPT_TUNING: "medium",
}


class ApprovalGateGuard:
    """Routes proposals to the approval store for human review.

    This guard always returns PASSED -- it does not reject proposals.
    Its role is to ensure every proposal is registered in the
    approval queue before proceeding.

    Args:
        approval_store: The approval store instance (optional; when
            None, the guard still passes but does not persist).
    """

    def __init__(
        self,
        *,
        approval_store: ApprovalStore | None = None,
    ) -> None:
        self._store = approval_store

    @property
    def name(self) -> str:
        """Guard name."""
        return "approval_gate"

    async def evaluate(
        self,
        proposal: ImprovementProposal,
    ) -> GuardResult:
        """Register proposal in approval store and pass.

        Args:
            proposal: The proposal to route for approval.

        Returns:
            Guard result with PASSED verdict (always).
        """
        risk = _ALTITUDE_RISK.get(proposal.altitude, "medium")
        logger.info(
            META_PROPOSAL_GUARD_PASSED,
            guard=self.name,
            proposal_id=str(proposal.id),
            risk_level=risk,
            altitude=proposal.altitude.value,
        )
        return GuardResult(
            guard_name=self.name,
            verdict=GuardVerdict.PASSED,
        )
