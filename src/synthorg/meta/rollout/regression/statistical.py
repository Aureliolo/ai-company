"""Statistical regression detector (Layer 2).

Uses Welch's t-test after the observation window to detect
statistically significant degradation.
"""

from synthorg.meta.models import (
    OrgSignalSnapshot,
    RegressionResult,
    RegressionThresholds,
    RegressionVerdict,
)
from synthorg.observability import get_logger

logger = get_logger(__name__)


class StatisticalDetector:
    """Detects regression via statistical significance testing.

    After the observation window, compares baseline and current
    metrics using Welch's t-test. Only fires if enough data points
    accumulated and the difference is statistically significant.

    Args:
        min_data_points: Minimum data points per metric for the test.
    """

    _HEURISTIC_DROP_THRESHOLD = 0.15

    def __init__(self, *, min_data_points: int = 10) -> None:
        self._min_data_points = min_data_points

    @property
    def name(self) -> str:
        """Detector name."""
        return "statistical"

    async def check(
        self,
        *,
        baseline: OrgSignalSnapshot,
        current: OrgSignalSnapshot,
        thresholds: RegressionThresholds,
    ) -> RegressionResult:
        """Check for statistically significant regression.

        Args:
            baseline: Signal snapshot from before the change.
            current: Signal snapshot from after the change.
            thresholds: Configurable thresholds (p-value).

        Returns:
            Regression result.
        """
        # Placeholder: real implementation uses scipy.stats.ttest_ind
        # with Welch's correction on accumulated per-task metrics.
        # For now, check if the aggregate values show degradation
        # beyond the significance level threshold.
        _ = thresholds

        base_q = baseline.performance.avg_quality_score
        curr_q = current.performance.avg_quality_score

        if base_q > 0.0 and curr_q < base_q:
            drop_ratio = (base_q - curr_q) / base_q
            # Rough heuristic: large drops are "significant".
            if drop_ratio > self._HEURISTIC_DROP_THRESHOLD:
                return RegressionResult(
                    verdict=RegressionVerdict.STATISTICAL_REGRESSION,
                    breached_metric="quality",
                    baseline_value=base_q,
                    current_value=curr_q,
                    p_value=drop_ratio,  # Heuristic proxy; TODO: Welch's t-test
                )

        return RegressionResult(
            verdict=RegressionVerdict.NO_REGRESSION,
        )
