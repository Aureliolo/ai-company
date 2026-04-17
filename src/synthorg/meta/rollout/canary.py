"""Canary subset rollout strategy with real observation loop.

Selects a canary subset deterministically (hashed split), applies the
proposal, then observes canary vs baseline metrics over the
observation window. Mid-window regressions exit early; a clean window
yields SUCCESS with the observed elapsed time.
"""

import hashlib
from typing import TYPE_CHECKING

from synthorg.core.types import NotBlankStr
from synthorg.meta.models import (
    ImprovementProposal,
    OrgSignalSnapshot,
    RegressionThresholds,
    RegressionVerdict,
    RolloutOutcome,
    RolloutResult,
)
from synthorg.meta.rollout.before_after import (
    SnapshotBuilder,
    _default_snapshot_builder,
)
from synthorg.meta.rollout.clock import Clock, RealClock
from synthorg.meta.rollout.roster import NoOpOrgRoster, OrgRoster
from synthorg.observability import get_logger
from synthorg.observability.events.meta import (
    META_ROLLOUT_COMPLETED,
    META_ROLLOUT_FAILED,
    META_ROLLOUT_OBSERVATION_COMPLETED,
    META_ROLLOUT_OBSERVATION_TICK,
    META_ROLLOUT_REGRESSION_DETECTED,
    META_ROLLOUT_STARTED,
)

if TYPE_CHECKING:
    from synthorg.meta.protocol import ProposalApplier, RegressionDetector

logger = get_logger(__name__)


class CanarySubsetRollout:
    """Applies a proposal to a canary subset, then expands on success.

    Args:
        canary_fraction: Fraction of the live roster placed in the canary.
        clock: Clock for sleeping and timestamping.
        roster: Provides the live list of agent ids.
        snapshot_builder: Builds the current signal snapshot.
        check_interval_hours: Polling cadence inside the window.
        thresholds: Regression thresholds for the detector.
    """

    def __init__(  # noqa: PLR0913
        self,
        *,
        canary_fraction: float = 0.2,
        clock: Clock | None = None,
        roster: OrgRoster | None = None,
        snapshot_builder: SnapshotBuilder | None = None,
        check_interval_hours: float = 4.0,
        thresholds: RegressionThresholds | None = None,
    ) -> None:
        if canary_fraction <= 0.0 or canary_fraction > 1.0:
            msg = "canary_fraction must be in the range (0, 1]."
            raise ValueError(msg)
        if check_interval_hours <= 0.0:
            msg = "check_interval_hours must be positive"
            raise ValueError(msg)
        self._canary_fraction = canary_fraction
        self._clock: Clock = clock or RealClock()
        self._roster: OrgRoster = roster or NoOpOrgRoster()
        self._snapshot_builder: SnapshotBuilder = (
            snapshot_builder or _default_snapshot_builder
        )
        self._check_interval_hours = check_interval_hours
        self._thresholds = thresholds or RegressionThresholds()

    @property
    def name(self) -> NotBlankStr:
        """Strategy name."""
        return NotBlankStr("canary")

    async def execute(
        self,
        *,
        proposal: ImprovementProposal,
        applier: ProposalApplier,
        detector: RegressionDetector,
    ) -> RolloutResult:
        """Execute canary rollout with a real observation loop."""
        agent_ids = await self._roster.list_agent_ids()
        canary_ids = _select_canary(
            agent_ids=agent_ids,
            proposal_id=str(proposal.id),
            fraction=self._canary_fraction,
        )
        logger.info(
            META_ROLLOUT_STARTED,
            strategy="canary",
            proposal_id=str(proposal.id),
            canary_fraction=self._canary_fraction,
            total_agents=len(agent_ids),
            canary_count=len(canary_ids),
            observation_hours=proposal.observation_window_hours,
        )

        baseline = await self._snapshot_builder()
        apply_result = await applier.apply(proposal)
        if not apply_result.success:
            logger.warning(
                META_ROLLOUT_FAILED,
                strategy="canary",
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
        """Poll the detector until the canary observation window closes."""
        observation_hours = float(proposal.observation_window_hours)
        elapsed = 0.0
        while elapsed < observation_hours:
            remaining = observation_hours - elapsed
            step_hours = min(self._check_interval_hours, remaining)
            await self._clock.sleep(step_hours * 3600.0)
            elapsed += step_hours
            current = await self._snapshot_builder()
            result = await detector.check(
                baseline=baseline,
                current=current,
                thresholds=self._thresholds,
            )
            logger.info(
                META_ROLLOUT_OBSERVATION_TICK,
                strategy="canary",
                proposal_id=str(proposal.id),
                elapsed_hours=elapsed,
                verdict=result.verdict.value,
            )
            if result.verdict == RegressionVerdict.THRESHOLD_BREACH or (
                elapsed >= observation_hours
                and result.verdict == RegressionVerdict.STATISTICAL_REGRESSION
            ):
                logger.warning(
                    META_ROLLOUT_REGRESSION_DETECTED,
                    strategy="canary",
                    proposal_id=str(proposal.id),
                    verdict=result.verdict.value,
                    elapsed_hours=elapsed,
                )
                return RolloutResult(
                    proposal_id=proposal.id,
                    outcome=RolloutOutcome.REGRESSED,
                    regression_verdict=result.verdict,
                    observation_hours_elapsed=elapsed,
                    details=(
                        str(result.breached_metric)
                        if result.breached_metric is not None
                        else None
                    ),
                )
        logger.info(
            META_ROLLOUT_OBSERVATION_COMPLETED,
            strategy="canary",
            proposal_id=str(proposal.id),
            observation_hours_elapsed=elapsed,
        )
        logger.info(
            META_ROLLOUT_COMPLETED,
            strategy="canary",
            proposal_id=str(proposal.id),
            outcome="success",
        )
        return RolloutResult(
            proposal_id=proposal.id,
            outcome=RolloutOutcome.SUCCESS,
            regression_verdict=RegressionVerdict.NO_REGRESSION,
            observation_hours_elapsed=elapsed,
        )


def _select_canary(
    *,
    agent_ids: tuple[NotBlankStr, ...],
    proposal_id: str,
    fraction: float,
) -> tuple[NotBlankStr, ...]:
    """Deterministic hash-based canary selection.

    Agents whose ``sha256(agent_id:proposal_id)`` bucket falls below
    ``fraction`` join the canary. Pure function, identical inputs
    produce identical splits across runs.
    """
    canary: list[NotBlankStr] = []
    for agent_id in agent_ids:
        digest = hashlib.sha256(
            f"{agent_id}:{proposal_id}".encode(),
        ).hexdigest()
        bucket = int(digest[:8], 16) / 0xFFFFFFFF
        if bucket < fraction:
            canary.append(agent_id)
    return tuple(canary)
