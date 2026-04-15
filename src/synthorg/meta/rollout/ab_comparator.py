"""A/B test group metrics comparator.

Compares control vs treatment group metrics using a two-layer
approach: threshold check for catastrophic regression, then
statistical heuristic for subtle improvement detection.
"""

from typing import TYPE_CHECKING

from synthorg.meta.rollout.ab_models import (
    ABTestComparison,
    ABTestVerdict,
    GroupMetrics,
)
from synthorg.observability import get_logger
from synthorg.observability.events.meta import (
    META_ABTEST_INCONCLUSIVE,
    META_ABTEST_TREATMENT_REGRESSED,
    META_ABTEST_WINNER_DECLARED,
)

if TYPE_CHECKING:
    from synthorg.meta.models import RegressionThresholds

logger = get_logger(__name__)

_IMPROVEMENT_THRESHOLD = 0.15


class ABTestComparator:
    """Compares control vs treatment group metrics.

    Layer 1: Threshold check -- treatment catastrophically worse
    on any primary metric triggers immediate TREATMENT_REGRESSED.

    Layer 2: Statistical heuristic -- if treatment shows meaningful
    improvement (effect > threshold), declares TREATMENT_WINS.

    Otherwise returns INCONCLUSIVE.

    Args:
        min_observations: Minimum metric samples per group
            before comparison is meaningful.
    """

    def __init__(self, *, min_observations: int = 10) -> None:
        self._min_observations = min_observations

    async def compare(
        self,
        *,
        control: GroupMetrics,
        treatment: GroupMetrics,
        thresholds: RegressionThresholds,
    ) -> ABTestComparison:
        """Compare control and treatment group metrics.

        Args:
            control: Metrics from the control group.
            treatment: Metrics from the treatment group.
            thresholds: Regression thresholds for breach detection.

        Returns:
            Comparison result with verdict, effect size, and p-value.
        """
        # Insufficient data -- cannot draw conclusions.
        if (
            control.observation_count < self._min_observations
            or treatment.observation_count < self._min_observations
        ):
            logger.info(
                META_ABTEST_INCONCLUSIVE,
                reason="insufficient_observations",
                control_obs=control.observation_count,
                treatment_obs=treatment.observation_count,
                min_required=self._min_observations,
            )
            return ABTestComparison(
                verdict=ABTestVerdict.INCONCLUSIVE,
                control_metrics=control,
                treatment_metrics=treatment,
            )

        # Layer 1: Check for treatment regression on each metric.
        regressed = _check_regressions(control, treatment, thresholds)
        if regressed:
            logger.warning(
                META_ABTEST_TREATMENT_REGRESSED,
                regressed_metrics=list(regressed),
            )
            return ABTestComparison(
                verdict=ABTestVerdict.TREATMENT_REGRESSED,
                control_metrics=control,
                treatment_metrics=treatment,
                regressed_metrics=tuple(regressed),
            )

        # Layer 2: Check for treatment improvement.
        effect, p_value = _compute_effect(control, treatment)
        if effect > _IMPROVEMENT_THRESHOLD:
            logger.info(
                META_ABTEST_WINNER_DECLARED,
                winner="treatment",
                effect_size=effect,
                p_value=p_value,
            )
            return ABTestComparison(
                verdict=ABTestVerdict.TREATMENT_WINS,
                control_metrics=control,
                treatment_metrics=treatment,
                effect_size=effect,
                p_value=p_value,
            )

        # No significant difference.
        logger.info(
            META_ABTEST_INCONCLUSIVE,
            reason="no_significant_difference",
            effect_size=effect,
        )
        return ABTestComparison(
            verdict=ABTestVerdict.INCONCLUSIVE,
            control_metrics=control,
            treatment_metrics=treatment,
            effect_size=effect,
            p_value=p_value,
        )


def _check_regressions(
    control: GroupMetrics,
    treatment: GroupMetrics,
    thresholds: RegressionThresholds,
) -> list[str]:
    """Check if treatment regressed beyond thresholds."""
    regressed: list[str] = []

    # Quality drop (lower is worse).
    if control.avg_quality_score > 0.0:
        drop = (
            control.avg_quality_score - treatment.avg_quality_score
        ) / control.avg_quality_score
        if drop > thresholds.quality_drop:
            regressed.append("quality")

    # Success rate drop (lower is worse).
    if control.avg_success_rate > 0.0:
        drop = (
            control.avg_success_rate - treatment.avg_success_rate
        ) / control.avg_success_rate
        if drop > thresholds.success_rate_drop:
            regressed.append("success_rate")

    # Cost increase (higher is worse).
    if control.total_spend_usd > 0.0:
        increase = (
            treatment.total_spend_usd - control.total_spend_usd
        ) / control.total_spend_usd
        if increase > thresholds.cost_increase:
            regressed.append("cost")

    return regressed


def _compute_effect(
    control: GroupMetrics,
    treatment: GroupMetrics,
) -> tuple[float, float]:
    """Compute heuristic effect size and p-value proxy.

    Returns:
        Tuple of (effect_size, p_value_proxy). Real implementation
        would use scipy.stats.ttest_ind with Welch's correction.
    """
    # Heuristic: use quality improvement ratio as effect proxy.
    if control.avg_quality_score > 0.0:
        improvement = (
            treatment.avg_quality_score - control.avg_quality_score
        ) / control.avg_quality_score
    else:
        improvement = 0.0

    # P-value proxy: inverse of improvement magnitude.
    # Real implementation would compute actual Welch's t-test.
    effect = max(improvement, 0.0)
    p_value = max(0.01, 1.0 - effect * 5.0) if effect > 0.0 else 1.0

    return effect, p_value
