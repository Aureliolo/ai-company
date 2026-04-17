"""Before/after rollout strategy with periodic regression checks.

Applies the proposal to the whole org, captures a baseline snapshot,
then samples the current signal snapshot at ``check_interval_hours``
over the proposal's ``observation_window_hours``. Regression verdicts
terminate the loop immediately. A clean window yields SUCCESS with
the observed elapsed time.
"""

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from synthorg.core.types import NotBlankStr
from synthorg.meta.models import (
    ImprovementProposal,
    OrgBudgetSummary,
    OrgCoordinationSummary,
    OrgErrorSummary,
    OrgEvolutionSummary,
    OrgPerformanceSummary,
    OrgScalingSummary,
    OrgSignalSnapshot,
    OrgTelemetrySummary,
    RegressionThresholds,
    RolloutOutcome,
    RolloutResult,
)
from synthorg.meta.rollout._observation import observe_until_verdict
from synthorg.meta.rollout.clock import Clock, RealClock
from synthorg.observability import get_logger
from synthorg.observability.events.meta import (
    META_ROLLOUT_FAILED,
    META_ROLLOUT_STARTED,
)

if TYPE_CHECKING:
    from synthorg.meta.protocol import ProposalApplier, RegressionDetector

logger = get_logger(__name__)

SnapshotBuilder = Callable[[], Awaitable[OrgSignalSnapshot]]
"""Coroutine producing the current org-wide signal snapshot."""


async def _default_snapshot_builder() -> OrgSignalSnapshot:
    """Empty snapshot used when no real builder is wired."""
    return OrgSignalSnapshot(
        performance=OrgPerformanceSummary(
            avg_quality_score=0.0,
            avg_success_rate=0.0,
            avg_collaboration_score=0.0,
            agent_count=0,
        ),
        budget=OrgBudgetSummary(
            total_spend=0.0,
            productive_ratio=0.0,
            coordination_ratio=0.0,
            system_ratio=0.0,
            forecast_confidence=0.0,
            orchestration_overhead=0.0,
        ),
        coordination=OrgCoordinationSummary(),
        scaling=OrgScalingSummary(),
        errors=OrgErrorSummary(),
        evolution=OrgEvolutionSummary(),
        telemetry=OrgTelemetrySummary(),
    )


class BeforeAfterRollout:
    """Applies a proposal to the whole org with periodic regression checks.

    Args:
        clock: Clock for sleeping and timestamping (defaults to wall clock).
        snapshot_builder: Async callable returning the current snapshot.
        check_interval_hours: How often to poll the detector mid-window.
        thresholds: Regression thresholds forwarded to the detector.
    """

    def __init__(
        self,
        *,
        clock: Clock | None = None,
        snapshot_builder: SnapshotBuilder | None = None,
        check_interval_hours: float = 4.0,
        thresholds: RegressionThresholds | None = None,
    ) -> None:
        if check_interval_hours <= 0.0:
            msg = "check_interval_hours must be positive"
            raise ValueError(msg)
        self._clock: Clock = clock or RealClock()
        self._snapshot_builder: SnapshotBuilder = (
            snapshot_builder or _default_snapshot_builder
        )
        self._check_interval_hours = check_interval_hours
        self._thresholds = thresholds or RegressionThresholds()

    @property
    def name(self) -> NotBlankStr:
        """Strategy name."""
        return NotBlankStr("before_after")

    async def execute(
        self,
        *,
        proposal: ImprovementProposal,
        applier: ProposalApplier,
        detector: RegressionDetector,
    ) -> RolloutResult:
        """Execute the before/after rollout with a real observation loop."""
        logger.info(
            META_ROLLOUT_STARTED,
            strategy="before_after",
            proposal_id=str(proposal.id),
            observation_hours=proposal.observation_window_hours,
            check_interval_hours=self._check_interval_hours,
        )

        baseline = await self._snapshot_builder()
        apply_result = await applier.apply(proposal)
        if not apply_result.success:
            logger.warning(
                META_ROLLOUT_FAILED,
                strategy="before_after",
                proposal_id=str(proposal.id),
                error=apply_result.error_message,
            )
            return RolloutResult(
                proposal_id=proposal.id,
                outcome=RolloutOutcome.FAILED,
                observation_hours_elapsed=0.0,
                details=apply_result.error_message,
            )

        return await self._observe_window(
            proposal=proposal,
            baseline=baseline,
            detector=detector,
        )

    async def _observe_window(
        self,
        *,
        proposal: ImprovementProposal,
        baseline: OrgSignalSnapshot,
        detector: RegressionDetector,
    ) -> RolloutResult:
        """Poll the detector until the observation window closes."""
        return await observe_until_verdict(
            proposal=proposal,
            baseline=baseline,
            detector=detector,
            clock=self._clock,
            snapshot_builder=self._snapshot_builder,
            check_interval_hours=self._check_interval_hours,
            thresholds=self._thresholds,
            strategy_name="before_after",
        )
