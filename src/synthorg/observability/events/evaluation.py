"""Evaluation framework event constants for structured logging.

Constants follow the ``eval.<subject>.<action>`` naming convention
and are passed as the first argument to structured log calls.
"""

from typing import Final

EVAL_REPORT_COMPUTED: Final[str] = "eval.report.computed"
EVAL_PILLAR_SCORED: Final[str] = "eval.pillar.scored"
EVAL_PILLAR_SKIPPED: Final[str] = "eval.pillar.skipped"
EVAL_PILLAR_INSUFFICIENT_DATA: Final[str] = "eval.pillar.insufficient_data"
EVAL_METRIC_SKIPPED: Final[str] = "eval.metric.skipped"
EVAL_FEEDBACK_RECORDED: Final[str] = "eval.feedback.recorded"
EVAL_CALIBRATION_DRIFT_HIGH: Final[str] = "eval.calibration.drift_high"
EVAL_WEIGHTS_REDISTRIBUTED: Final[str] = "eval.weights.redistributed"
