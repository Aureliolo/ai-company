"""Performance inflection event constants for structured logging.

Constants follow the ``perf.inflection.<action>`` naming convention
and are passed as the first argument to structured log calls.
"""

from typing import Final

PERF_INFLECTION_DETECTED: Final[str] = "perf.inflection.detected"
PERF_INFLECTION_EMISSION_FAILED: Final[str] = "perf.inflection.emission_failed"
