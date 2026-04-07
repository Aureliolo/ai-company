"""Health monitoring pipeline event constants."""

from typing import Final

HEALTH_TICKET_EMITTED: Final[str] = "execution.health.ticket_emitted"
HEALTH_TICKET_DISMISSED: Final[str] = "execution.health.ticket_dismissed"
HEALTH_TICKET_ESCALATED: Final[str] = "execution.health.ticket_escalated"
HEALTH_PIPELINE_ERROR: Final[str] = "execution.health.pipeline_error"
HEALTH_TRIAGE_CONFIG_ERROR: Final[str] = "execution.health.triage_config_error"
