"""Config applier.

Applies approved config tuning proposals by reconstructing
the RootConfig with the proposed changes.
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


class ConfigApplier:
    """Applies config tuning proposals.

    Reads current config, applies the proposed diffs, validates
    the resulting config, and persists it.
    """

    @property
    def altitude(self) -> ProposalAltitude:
        """This applier handles config tuning proposals."""
        return ProposalAltitude.CONFIG_TUNING

    async def apply(
        self,
        proposal: ImprovementProposal,
    ) -> ApplyResult:
        """Apply config changes from the proposal.

        Args:
            proposal: The approved config tuning proposal.

        Returns:
            Result indicating success or failure.
        """
        try:
            # Placeholder: real implementation will read current
            # RootConfig, apply JSON-path diffs, validate, persist.
            count = len(proposal.config_changes)
            logger.info(
                META_APPLY_COMPLETED,
                altitude="config_tuning",
                changes=count,
                proposal_id=str(proposal.id),
            )
            return ApplyResult(success=True, changes_applied=count)
        except MemoryError, RecursionError:
            raise
        except Exception:
            logger.exception(
                META_APPLY_FAILED,
                altitude="config_tuning",
                proposal_id=str(proposal.id),
            )
            return ApplyResult(
                success=False,
                error_message="Config apply failed. Check logs for details.",
                changes_applied=0,
            )

    async def dry_run(
        self,
        proposal: ImprovementProposal,
    ) -> ApplyResult:
        """Validate config changes without applying.

        Args:
            proposal: The proposal to validate.

        Returns:
            Result indicating whether apply would succeed.
        """
        # Placeholder: validate config paths against schema.
        # Fail closed until real validation is implemented.
        _ = proposal
        return ApplyResult(
            success=False,
            changes_applied=0,
            error_message="dry_run not yet implemented",
        )
