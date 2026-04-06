"""Coordination metrics event constants."""

from typing import Final

COORD_METRICS_AMDAHL_COMPUTED: Final[str] = "coordination.metrics.amdahl_computed"
COORD_METRICS_STRAGGLER_GAP_COMPUTED: Final[str] = (
    "coordination.metrics.straggler_gap_computed"
)
COORD_METRICS_TOKEN_SPEEDUP_ALERT: Final[str] = (
    "coordination.metrics.token_speedup_alert"  # noqa: S105
)
COORD_METRICS_MESSAGE_OVERHEAD_ALERT: Final[str] = (
    "coordination.metrics.message_overhead_alert"
)
