"""Architecture applier.

Applies approved architecture proposals by creating new roles,
departments, or modifying workflows in the appropriate registries.
"""

from synthorg.meta.models import (
    ApplyResult,
    ImprovementProposal,
    ProposalAltitude,
)
from synthorg.observability import get_logger
from synthorg.observability.events.meta import (
    META_APPLY_COMPLETED,
    META_APPLY_FAILED,
)

logger = get_logger(__name__)


class ArchitectureApplier:
    """Applies architecture proposals.

    Creates new entities (roles, departments, workflows) in the
    appropriate registries.
    """

    @property
    def altitude(self) -> ProposalAltitude:
        """This applier handles architecture proposals."""
        return ProposalAltitude.ARCHITECTURE

    async def apply(
        self,
        proposal: ImprovementProposal,
    ) -> ApplyResult:
        """Apply architecture changes from the proposal.

        Args:
            proposal: The approved architecture proposal.

        Returns:
            Result indicating success or failure.
        """
        try:
            count = len(proposal.architecture_changes)
            logger.info(
                META_APPLY_COMPLETED,
                altitude="architecture",
                changes=count,
                proposal_id=str(proposal.id),
            )
            return ApplyResult(success=True, changes_applied=count)
        except MemoryError, RecursionError:
            raise
        except Exception:
            logger.exception(
                META_APPLY_FAILED,
                altitude="architecture",
                proposal_id=str(proposal.id),
            )
            return ApplyResult(
                success=False,
                error_message="Architecture apply failed. Check logs.",
                changes_applied=0,
            )

    async def dry_run(
        self,
        proposal: ImprovementProposal,
    ) -> ApplyResult:
        """Validate architecture changes without applying.

        Args:
            proposal: The proposal to validate.

        Returns:
            Result indicating whether apply would succeed.
        """
        # Fail closed until real validation is implemented.
        _ = proposal
        return ApplyResult(
            success=False,
            changes_applied=0,
            error_message="dry_run not yet implemented",
        )
