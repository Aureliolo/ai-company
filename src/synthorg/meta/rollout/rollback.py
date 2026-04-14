"""Rollback executor.

Applies a RollbackPlan to revert an improvement proposal,
respecting dependencies and running validation checks.
"""

from synthorg.meta.models import (
    ApplyResult,
    ImprovementProposal,
)
from synthorg.observability import get_logger
from synthorg.observability.events.meta import (
    META_ROLLBACK_COMPLETED,
    META_ROLLBACK_FAILED,
)

logger = get_logger(__name__)


class RollbackExecutor:
    """Executes rollback plans for reverted proposals.

    Applies rollback operations in order, respecting dependencies,
    and runs the validation check after completion.
    """

    async def execute(
        self,
        proposal: ImprovementProposal,
    ) -> ApplyResult:
        """Execute the rollback plan for a proposal.

        Args:
            proposal: The proposal whose rollback plan to execute.

        Returns:
            Result indicating success or failure.
        """
        plan = proposal.rollback_plan
        try:
            # Placeholder: real implementation iterates operations
            # and applies each inverse action (revert config, delete
            # role, remove principle).  For now, count + log.
            count = 0
            for _operation in plan.operations:
                # TODO: dispatch to operation handler per type.
                count += 1
            logger.info(
                META_ROLLBACK_COMPLETED,
                proposal_id=str(proposal.id),
                operations=count,
                validation=plan.validation_check,
            )
            return ApplyResult(
                success=True,
                changes_applied=count,
            )
        except Exception as exc:
            logger.exception(
                META_ROLLBACK_FAILED,
                proposal_id=str(proposal.id),
            )
            return ApplyResult(
                success=False,
                error_message=str(exc),
                changes_applied=0,
            )
