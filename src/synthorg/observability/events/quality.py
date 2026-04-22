"""Step-level quality signal event constants."""

from typing import Final

QUALITY_STEP_CLASSIFIED: Final[str] = "execution.quality.step_classified"
QUALITY_CLASSIFIER_CONFIG_INVALID: Final[str] = (
    "execution.quality.classifier_config_invalid"
)
QUALITY_ACCURACY_EFFORT_COMPUTED: Final[str] = (
    "execution.quality.accuracy_effort_computed"
)
QUALITY_WEAK_MODEL_WARNING: Final[str] = "execution.quality.weak_model_warning"
