"""Stagnation detection event constants."""

from typing import Final

STAGNATION_CHECK_PERFORMED: Final[str] = "execution.stagnation.check_performed"
STAGNATION_DETECTED: Final[str] = "execution.stagnation.detected"
STAGNATION_CORRECTION_INJECTED: Final[str] = "execution.stagnation.correction_injected"
STAGNATION_TERMINATED: Final[str] = "execution.stagnation.terminated"
QUALITY_STAGNATION_DETECTED: Final[str] = "execution.stagnation.quality_detected"
STAGNATION_QUALITY_EROSION_CONFIG_ERROR: Final[str] = (
    "execution.stagnation.quality_erosion_config_error"
)
