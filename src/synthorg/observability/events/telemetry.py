"""Product telemetry event constants."""

from typing import Final

TELEMETRY_HEARTBEAT_SENT: Final[str] = "telemetry.heartbeat.sent"
TELEMETRY_SESSION_SUMMARY_SENT: Final[str] = "telemetry.session_summary.sent"
TELEMETRY_REPORT_FAILED: Final[str] = "telemetry.report.failed"
TELEMETRY_PRIVACY_VIOLATION: Final[str] = "telemetry.privacy.violation"
TELEMETRY_ENABLED: Final[str] = "telemetry.enabled"
TELEMETRY_DISABLED: Final[str] = "telemetry.disabled"
TELEMETRY_REPORTER_INITIALIZED: Final[str] = "telemetry.reporter.initialized"
