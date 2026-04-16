"""Cross-deployment analytics for self-improvement patterns.

Opt-in, privacy-preserving telemetry that aggregates anonymized
improvement outcomes across multiple SynthOrg deployments to
identify patterns and recommend improved default thresholds.
"""

from synthorg.meta.telemetry.config import CrossDeploymentAnalyticsConfig
from synthorg.meta.telemetry.models import (
    AggregatedPattern,
    AnonymizedOutcomeEvent,
    EventBatch,
    ThresholdRecommendation,
)
from synthorg.meta.telemetry.protocol import (
    AnalyticsCollector,
    AnalyticsEmitter,
    RecommendationProvider,
)

__all__ = [
    "AggregatedPattern",
    "AnalyticsCollector",
    "AnalyticsEmitter",
    "AnonymizedOutcomeEvent",
    "CrossDeploymentAnalyticsConfig",
    "EventBatch",
    "RecommendationProvider",
    "ThresholdRecommendation",
]
