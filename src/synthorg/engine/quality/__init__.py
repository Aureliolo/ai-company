"""Step-level quality signals for engine execution.

Provides ternary step classification (correct/neutral/incorrect),
accuracy-effort ratio computation, and a pluggable classifier protocol.
"""

from synthorg.engine.quality.classifier import (
    RuleBasedStepClassifier,
    StepQualityClassifier,
)
from synthorg.engine.quality.effort import compute_accuracy_effort
from synthorg.engine.quality.models import (
    AccuracyEffortRatio,
    StepQuality,
    StepQualitySignal,
)

__all__ = [
    "AccuracyEffortRatio",
    "RuleBasedStepClassifier",
    "StepQuality",
    "StepQualityClassifier",
    "StepQualitySignal",
    "compute_accuracy_effort",
]
