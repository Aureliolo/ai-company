"""Threshold recommendation generator.

Analyzes cross-deployment patterns and suggests threshold
adjustments for built-in rules based on observed outcomes.
"""

from typing import TYPE_CHECKING

from synthorg.core.types import NotBlankStr
from synthorg.meta.telemetry.models import ThresholdRecommendation
from synthorg.observability import get_logger
from synthorg.observability.events.cross_deployment import (
    XDEPLOY_RECOMMENDATION_GENERATED,
)

if TYPE_CHECKING:
    from synthorg.meta.telemetry.models import AggregatedPattern
    from synthorg.meta.telemetry.protocol import AnalyticsCollector

logger = get_logger(__name__)

# Thresholds for recommendation generation.
_HIGH_APPROVAL_RATE = 0.7
_HIGH_SUCCESS_RATE = 0.7
_LOW_APPROVAL_RATE = 0.3
_MIN_OBSERVATIONS_FOR_RECOMMENDATION = 10

# Mapping of rule names to their configurable threshold fields
# and current defaults. Used to generate concrete recommendations.
_RULE_THRESHOLD_MAP: dict[str, tuple[str, float]] = {
    "quality_declining": ("quality_drop_threshold", 5.0),
    "success_rate_drop": ("success_rate_threshold", 0.7),
    "budget_overrun": ("days_until_exhausted_threshold", 14.0),
    "coordination_cost_ratio": ("coordination_ratio_threshold", 0.4),
    "coordination_overhead": ("overhead_pct_threshold", 35.0),
    "straggler_bottleneck": ("straggler_gap_ratio_threshold", 2.0),
    "redundancy": ("redundancy_rate_threshold", 0.3),
    "scaling_failure": ("scaling_failure_rate_threshold", 0.5),
    "error_spike": ("error_findings_threshold", 10.0),
}


class DefaultThresholdRecommender:
    """Generates threshold recommendations from aggregated patterns.

    Analyzes cross-deployment patterns and recommends threshold
    adjustments when consistent outcomes are observed:

    - High approval + high success rate: threshold may be too
      conservative (fires correctly, proposals succeed). Recommend
      relaxing slightly.
    - Low approval rate: threshold may be too aggressive (fires
      often but humans reject). Recommend tightening.
    """

    async def get_recommendations(
        self,
        *,
        collector: AnalyticsCollector,
    ) -> tuple[ThresholdRecommendation, ...]:
        """Generate recommendations from collected data.

        Args:
            collector: Collector to query patterns from.

        Returns:
            Threshold recommendations sorted by confidence.
        """
        patterns = await collector.query_patterns(min_deployments=3)
        recommendations: list[ThresholdRecommendation] = []

        for pattern in patterns:
            rec = self._evaluate_pattern(pattern)
            if rec is not None:
                recommendations.append(rec)

        recommendations.sort(key=lambda r: -r.confidence)

        if recommendations:
            logger.info(
                XDEPLOY_RECOMMENDATION_GENERATED,
                count=len(recommendations),
            )

        return tuple(recommendations)

    def _evaluate_pattern(
        self,
        pattern: AggregatedPattern,
    ) -> ThresholdRecommendation | None:
        """Evaluate a single pattern for threshold recommendation.

        Args:
            pattern: Aggregated cross-deployment pattern.

        Returns:
            A recommendation, or None if no adjustment is warranted.
        """
        threshold_info = _RULE_THRESHOLD_MAP.get(pattern.source_rule)
        if threshold_info is None:
            return None

        metric_name, current_default = threshold_info

        # High approval + high success: threshold may be too conservative.
        if (
            pattern.approval_rate >= _HIGH_APPROVAL_RATE
            and pattern.success_rate >= _HIGH_SUCCESS_RATE
            and pattern.total_events >= _MIN_OBSERVATIONS_FOR_RECOMMENDATION
        ):
            # Recommend relaxing by 10-20% based on confidence.
            adjustment = 0.1 + (0.1 * pattern.avg_confidence)
            recommended = current_default * (1.0 + adjustment)
            confidence = min(
                pattern.avg_confidence,
                pattern.deployment_count / 10.0,
            )
            return ThresholdRecommendation(
                rule_name=NotBlankStr(pattern.source_rule),
                metric_name=NotBlankStr(metric_name),
                current_default=current_default,
                recommended_value=round(recommended, 4),
                confidence=min(confidence, 1.0),
                based_on_deployments=pattern.deployment_count,
                based_on_observations=pattern.total_events,
                rationale=NotBlankStr(
                    f"Rule '{pattern.source_rule}' has "
                    f"{pattern.approval_rate:.0%} approval and "
                    f"{pattern.success_rate:.0%} success across "
                    f"{pattern.deployment_count} deployments. "
                    f"Threshold may be too conservative."
                ),
            )

        # Low approval: threshold may be too aggressive.
        if (
            pattern.approval_rate <= _LOW_APPROVAL_RATE
            and pattern.total_events >= _MIN_OBSERVATIONS_FOR_RECOMMENDATION
        ):
            adjustment = 0.1 + (0.1 * (1.0 - pattern.avg_confidence))
            recommended = current_default * (1.0 - adjustment)
            confidence = min(
                0.5 + (pattern.deployment_count / 20.0),
                1.0,
            )
            return ThresholdRecommendation(
                rule_name=NotBlankStr(pattern.source_rule),
                metric_name=NotBlankStr(metric_name),
                current_default=current_default,
                recommended_value=round(recommended, 4),
                confidence=confidence,
                based_on_deployments=pattern.deployment_count,
                based_on_observations=pattern.total_events,
                rationale=NotBlankStr(
                    f"Rule '{pattern.source_rule}' has only "
                    f"{pattern.approval_rate:.0%} approval across "
                    f"{pattern.deployment_count} deployments. "
                    f"Threshold may be too aggressive."
                ),
            )

        return None
