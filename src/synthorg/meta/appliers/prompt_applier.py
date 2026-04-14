"""Prompt applier.

Applies approved prompt tuning proposals by injecting or removing
constitutional principles in the strategy configuration.
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


class PromptApplier:
    """Applies prompt tuning proposals.

    Injects new constitutional principles into agent prompts
    via the ConstitutionalPrincipleConfig mechanism.
    """

    @property
    def altitude(self) -> ProposalAltitude:
        """This applier handles prompt tuning proposals."""
        return ProposalAltitude.PROMPT_TUNING

    async def apply(
        self,
        proposal: ImprovementProposal,
    ) -> ApplyResult:
        """Apply prompt changes from the proposal.

        Args:
            proposal: The approved prompt tuning proposal.

        Returns:
            Result indicating success or failure.
        """
        try:
            count = len(proposal.prompt_changes)
            logger.info(
                META_APPLY_COMPLETED,
                altitude="prompt_tuning",
                changes=count,
                proposal_id=str(proposal.id),
            )
            return ApplyResult(success=True, changes_applied=count)
        except MemoryError, RecursionError:
            raise
        except Exception:
            logger.exception(
                META_APPLY_FAILED,
                altitude="prompt_tuning",
                proposal_id=str(proposal.id),
            )
            return ApplyResult(
                success=False,
                error_message="Prompt apply failed. Check logs.",
                changes_applied=0,
            )

    async def dry_run(
        self,
        proposal: ImprovementProposal,
    ) -> ApplyResult:
        """Validate prompt changes without applying.

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
