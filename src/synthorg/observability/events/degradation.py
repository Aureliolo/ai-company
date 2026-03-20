"""Quota degradation event constants."""

from typing import Final

DEGRADATION_FALLBACK_STARTED: Final[str] = "degradation.fallback.started"
DEGRADATION_FALLBACK_PROVIDER_CHECKED: Final[str] = (
    "degradation.fallback.provider_checked"
)
DEGRADATION_FALLBACK_RESOLVED: Final[str] = "degradation.fallback.resolved"
DEGRADATION_FALLBACK_EXHAUSTED: Final[str] = "degradation.fallback.exhausted"
DEGRADATION_FALLBACK_CHECK_ERROR: Final[str] = "degradation.fallback.check_error"
DEGRADATION_QUEUE_STARTED: Final[str] = "degradation.queue.started"
DEGRADATION_QUEUE_WAITING: Final[str] = "degradation.queue.waiting"
DEGRADATION_QUEUE_RESUMED: Final[str] = "degradation.queue.resumed"
DEGRADATION_QUEUE_EXHAUSTED: Final[str] = "degradation.queue.exhausted"
DEGRADATION_QUEUE_WINDOW_ROTATED: Final[str] = "degradation.queue.window_rotated"
DEGRADATION_ALERT_RAISED: Final[str] = "degradation.alert.raised"
DEGRADATION_PROVIDER_SWAPPED: Final[str] = "degradation.provider_swapped"
