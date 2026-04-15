"""A/B test rollout strategy.

Splits the org into control and treatment groups, applies
the proposal to the treatment group only, and compares
group metrics statistically to declare a winner.
"""

import hashlib
from typing import TYPE_CHECKING

from synthorg.meta.models import (
    ImprovementProposal,
    RegressionThresholds,
    RegressionVerdict,
    RolloutOutcome,
    RolloutResult,
)
from synthorg.meta.rollout.ab_comparator import ABTestComparator
from synthorg.meta.rollout.ab_models import (
    ABTestGroup,
    ABTestVerdict,
    GroupAssignment,
    GroupMetrics,
)
from synthorg.observability import get_logger
from synthorg.observability.events.meta import (
    META_ABTEST_GROUPS_ASSIGNED,
    META_ABTEST_OBSERVATION_STARTED,
    META_ROLLOUT_COMPLETED,
    META_ROLLOUT_FAILED,
    META_ROLLOUT_STARTED,
)

if TYPE_CHECKING:
    from uuid import UUID

    from synthorg.meta.protocol import ProposalApplier, RegressionDetector

logger = get_logger(__name__)


class ABTestRollout:
    """A/B test rollout: split org, apply to treatment, compare.

    Splits agents into control (unchanged) and treatment (proposal
    applied) groups using deterministic hash-based assignment.
    After observation, compares group metrics to declare a winner.

    Args:
        control_fraction: Fraction of agents for control (default 0.5).
        min_agents_per_group: Minimum agents required per group.
        comparator: ABTestComparator instance (injectable for testing).
    """

    def __init__(
        self,
        *,
        control_fraction: float = 0.5,
        min_agents_per_group: int = 5,
        improvement_threshold: float = 0.15,
        comparator: ABTestComparator | None = None,
    ) -> None:
        if control_fraction <= 0.0 or control_fraction >= 1.0:
            msg = "control_fraction must be in the range (0, 1) exclusive."
            raise ValueError(msg)
        if min_agents_per_group < 1:
            msg = "min_agents_per_group must be >= 1."
            raise ValueError(msg)
        self._control_fraction = control_fraction
        self._min_agents_per_group = min_agents_per_group
        self._comparator = comparator or ABTestComparator(
            improvement_threshold=improvement_threshold,
        )

    @property
    def name(self) -> str:
        """Strategy name."""
        return "ab_test"

    async def execute(
        self,
        *,
        proposal: ImprovementProposal,
        applier: ProposalApplier,
        detector: RegressionDetector,
    ) -> RolloutResult:
        """Execute A/B test rollout.

        Args:
            proposal: The approved proposal.
            applier: Applier for the proposal's altitude.
            detector: Regression detector (unused; A/B uses comparator).

        Returns:
            Rollout result.
        """
        _ = detector  # A/B uses comparator for group comparison.
        logger.info(
            META_ROLLOUT_STARTED,
            strategy="ab_test",
            proposal_id=str(proposal.id),
            control_fraction=self._control_fraction,
        )

        assignment = _assign_and_validate(
            proposal,
            self._control_fraction,
            self._min_agents_per_group,
        )
        if assignment is None:
            return RolloutResult(
                proposal_id=proposal.id,
                outcome=RolloutOutcome.INCONCLUSIVE,
                observation_hours_elapsed=0.0,
                details="insufficient agents for A/B test groups",
            )

        result = await _apply_to_treatment(proposal, applier)
        if result is not None:
            return result

        return await self._compare_and_conclude(proposal, assignment)

    async def _compare_and_conclude(
        self,
        proposal: ImprovementProposal,
        assignment: GroupAssignment,
    ) -> RolloutResult:
        """Collect metrics and compare groups."""
        logger.info(
            META_ABTEST_OBSERVATION_STARTED,
            proposal_id=str(proposal.id),
            observation_hours=proposal.observation_window_hours,
        )

        # Placeholder: real impl observes over observation_window_hours.
        comparison = await self._comparator.compare(
            control=_stub_group_metrics(
                ABTestGroup.CONTROL,
                len(assignment.control_agent_ids),
            ),
            treatment=_stub_group_metrics(
                ABTestGroup.TREATMENT,
                len(assignment.treatment_agent_ids),
            ),
            thresholds=RegressionThresholds(),
        )

        outcome, verdict = _map_verdict(comparison.verdict)
        logger.info(
            META_ROLLOUT_COMPLETED,
            strategy="ab_test",
            proposal_id=str(proposal.id),
            outcome=outcome.value,
            ab_verdict=comparison.verdict.value,
        )
        return RolloutResult(
            proposal_id=proposal.id,
            outcome=outcome,
            regression_verdict=verdict,
            observation_hours_elapsed=0.0,
        )

    @staticmethod
    def assign_groups(
        agent_ids: tuple[str, ...],
        proposal_id: UUID,
        control_fraction: float,
    ) -> GroupAssignment:
        """Deterministically assign agents to control/treatment.

        Uses SHA-256 hash of ``agent_id:proposal_id`` to assign
        each agent. The hash is stable across runs for the same
        inputs, producing reproducible group splits.

        Args:
            agent_ids: All agent IDs to split.
            proposal_id: Proposal ID used as hash salt.
            control_fraction: Target fraction for control group.

        Returns:
            Group assignment with control and treatment agent IDs.
        """
        control: list[str] = []
        treatment: list[str] = []
        pid_str = str(proposal_id)

        for agent_id in agent_ids:
            digest = hashlib.sha256(
                f"{agent_id}:{pid_str}".encode(),
            ).hexdigest()
            # Use first 8 hex chars (32 bits) for bucket.
            bucket = int(digest[:8], 16) / 0xFFFFFFFF
            if bucket < control_fraction:
                control.append(agent_id)
            else:
                treatment.append(agent_id)

        return GroupAssignment(
            proposal_id=proposal_id,
            control_agent_ids=tuple(control),
            treatment_agent_ids=tuple(treatment),
            control_fraction=control_fraction,
        )


def _assign_and_validate(
    proposal: ImprovementProposal,
    control_fraction: float,
    min_agents: int,
) -> GroupAssignment | None:
    """Assign groups and validate minimum sizes.

    Returns None if either group is too small.
    """
    # Placeholder agent list; real impl gets from org.
    agent_ids = tuple(f"agent-{i}" for i in range(10))
    assignment = ABTestRollout.assign_groups(
        agent_ids,
        proposal.id,
        control_fraction,
    )
    logger.info(
        META_ABTEST_GROUPS_ASSIGNED,
        proposal_id=str(proposal.id),
        control_count=len(assignment.control_agent_ids),
        treatment_count=len(assignment.treatment_agent_ids),
    )

    if (
        len(assignment.control_agent_ids) < min_agents
        or len(assignment.treatment_agent_ids) < min_agents
    ):
        return None
    return assignment


async def _apply_to_treatment(
    proposal: ImprovementProposal,
    applier: ProposalApplier,
) -> RolloutResult | None:
    """Apply proposal to treatment group. Returns result on failure."""
    apply_result = await applier.apply(proposal)
    if not apply_result.success:
        logger.warning(
            META_ROLLOUT_FAILED,
            strategy="ab_test",
            proposal_id=str(proposal.id),
            error=apply_result.error_message,
        )
        return RolloutResult(
            proposal_id=proposal.id,
            outcome=RolloutOutcome.FAILED,
            observation_hours_elapsed=0.0,
            details=apply_result.error_message,
        )
    return None


def _stub_group_metrics(
    group: ABTestGroup,
    agent_count: int,
) -> GroupMetrics:
    """Generate stub metrics for a group (placeholder).

    Real implementation collects actual metrics from each group's
    agents during the observation window.
    """
    return GroupMetrics(
        group=group,
        agent_count=agent_count,
        observation_count=0,
        avg_quality_score=7.5,
        avg_success_rate=0.85,
        total_spend_usd=100.0,
    )


def _map_verdict(
    verdict: ABTestVerdict,
) -> tuple[RolloutOutcome, RegressionVerdict | None]:
    """Map ABTestVerdict to RolloutOutcome + RegressionVerdict."""
    if verdict == ABTestVerdict.TREATMENT_WINS:
        return RolloutOutcome.SUCCESS, RegressionVerdict.NO_REGRESSION
    if verdict in (
        ABTestVerdict.TREATMENT_REGRESSED,
        ABTestVerdict.CONTROL_WINS,
    ):
        return (
            RolloutOutcome.REGRESSED,
            RegressionVerdict.STATISTICAL_REGRESSION,
        )
    # INCONCLUSIVE
    return RolloutOutcome.INCONCLUSIVE, None
