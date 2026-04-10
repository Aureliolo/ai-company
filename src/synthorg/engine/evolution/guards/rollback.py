"""RollbackGuard -- monitors post-adaptation performance for regression."""

from synthorg.core.types import NotBlankStr
from synthorg.engine.evolution.models import AdaptationDecision, AdaptationProposal
from synthorg.observability import get_logger
from synthorg.observability.events.evolution import (
    EVOLUTION_ROLLBACK_TRIGGERED,
)

logger = get_logger(__name__)


class RollbackGuard:
    """Monitors post-adaptation performance for regression.

    The guard's ``evaluate()`` method always approves (pre-adaptation check).
    The ``check_regression()`` method is called post-adaptation to monitor
    for performance degradation and trigger rollback if needed.
    """

    def __init__(
        self,
        window_tasks: int = 20,
        regression_threshold: float = 0.1,
    ) -> None:
        """Initialize RollbackGuard.

        Args:
            window_tasks: Number of tasks to observe post-adaptation.
            regression_threshold: Quality drop threshold (0-1) to trigger rollback.
        """
        self._window_tasks = window_tasks
        self._regression_threshold = regression_threshold
        self._baselines: dict[str, float] = {}
        self._task_counts: dict[str, int] = {}

    @property
    def name(self) -> str:
        """Return guard name."""
        return "RollbackGuard"

    async def evaluate(
        self,
        proposal: AdaptationProposal,
    ) -> AdaptationDecision:
        """Evaluate the proposal (pre-adaptation check).

        Always approves. Post-adaptation rollback monitoring is done via
        ``check_regression()``.

        Args:
            proposal: The adaptation proposal to evaluate.

        Returns:
            Always approves.
        """
        return AdaptationDecision(
            proposal_id=proposal.id,
            approved=True,
            guard_name=self.name,
            reason="Pre-adaptation check passed; post-adaptation monitoring enabled",
        )

    def check_regression(
        self,
        agent_id: NotBlankStr,
        baseline_quality: float,
        current_quality: float,
    ) -> bool:
        """Check for performance regression post-adaptation.

        Args:
            agent_id: Target agent.
            baseline_quality: Quality score before adaptation.
            current_quality: Quality score after adaptation.

        Returns:
            True if regression detected, False otherwise.
        """
        quality_drop = baseline_quality - current_quality
        epsilon = 1e-9
        has_regression = quality_drop > (self._regression_threshold - epsilon)

        if has_regression:
            logger.warning(
                EVOLUTION_ROLLBACK_TRIGGERED,
                agent_id=agent_id,
                baseline_quality=baseline_quality,
                current_quality=current_quality,
                drop=quality_drop,
                threshold=self._regression_threshold,
            )

        self._baselines[agent_id] = baseline_quality
        self._task_counts[agent_id] = self._window_tasks

        return has_regression
