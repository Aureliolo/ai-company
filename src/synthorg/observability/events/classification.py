"""Classification pipeline event constants."""

from typing import Final

CLASSIFICATION_START: Final[str] = "classification.start"
CLASSIFICATION_COMPLETE: Final[str] = "classification.complete"
CLASSIFICATION_FINDING: Final[str] = "classification.finding"
CLASSIFICATION_ERROR: Final[str] = "classification.error"
CLASSIFICATION_SKIPPED: Final[str] = "classification.skipped"

# Per-detector lifecycle events
DETECTOR_START: Final[str] = "classification.detector.start"
DETECTOR_COMPLETE: Final[str] = "classification.detector.complete"
DETECTOR_ERROR: Final[str] = "classification.detector.error"

# Semantic detector cost and budget events
DETECTOR_BUDGET_EXHAUSTED: Final[str] = "classification.detector.budget_exhausted"
DETECTOR_COST_INCURRED: Final[str] = "classification.detector.cost_incurred"

# Sink and dedup events
CLASSIFICATION_SINK_ERROR: Final[str] = "classification.sink.error"
CLASSIFICATION_FINDING_DEDUPLICATED: Final[str] = "classification.finding.deduplicated"
