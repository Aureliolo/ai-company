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
        improvement_threshold: Minimum improvement ratio to
            declare treatment as winner.
    """

    def __init__(
        self,
        *,
        min_observations: int = 10,
        improvement_threshold: float = 0.15,
    ) -> None:
        self._min_observations = min_observations
        self._improvement_threshold = improvement_threshold

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
        if _insufficient_observations(
            control,
            treatment,
            self._min_observations,
        ):
            return _build_insufficient_result(
                control,
                treatment,
                self._min_observations,
            )

        regressed = _check_regressions(control, treatment, thresholds)
        if regressed:
            return _build_regression_result(
                control,
                treatment,
                regressed,
            )

        effect, p_value = _compute_effect(control, treatment)
        if effect > self._improvement_threshold:
            return _build_winner_result(
                control,
                treatment,
                effect,
                p_value,
            )

        return _build_no_difference_result(
            control,
            treatment,
            effect,
            p_value,
        )


def _insufficient_observations(
    control: GroupMetrics,
    treatment: GroupMetrics,
    min_obs: int,
) -> bool:
    """Check if either group has fewer observations than required."""
    return control.observation_count < min_obs or treatment.observation_count < min_obs


def _build_insufficient_result(
    control: GroupMetrics,
    treatment: GroupMetrics,
    min_obs: int,
) -> ABTestComparison:
    """Build INCONCLUSIVE result for insufficient observations."""
    logger.info(
        META_ABTEST_INCONCLUSIVE,
        reason="insufficient_observations",
        control_obs=control.observation_count,
        treatment_obs=treatment.observation_count,
        min_required=min_obs,
    )
    return ABTestComparison(
        verdict=ABTestVerdict.INCONCLUSIVE,
        control_metrics=control,
        treatment_metrics=treatment,
    )


def _build_regression_result(
    control: GroupMetrics,
    treatment: GroupMetrics,
    regressed: list[str],
) -> ABTestComparison:
    """Build TREATMENT_REGRESSED result."""
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


def _build_winner_result(
    control: GroupMetrics,
    treatment: GroupMetrics,
    effect: float,
    p_value: float,
) -> ABTestComparison:
    """Build TREATMENT_WINS result."""
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


def _build_no_difference_result(
    control: GroupMetrics,
    treatment: GroupMetrics,
    effect: float,
    p_value: float,
) -> ABTestComparison:
    """Build INCONCLUSIVE result for no significant difference."""
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
    if control.total_spend_usd == 0.0:
        if treatment.total_spend_usd > 0.0:
            regressed.append("cost")
    else:
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
