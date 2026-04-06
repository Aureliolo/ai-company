"""Notification subsystem event constants."""

from typing import Final

NOTIFICATION_DISPATCHED: Final[str] = "notification.dispatched"
NOTIFICATION_DISPATCH_FAILED: Final[str] = "notification.dispatch.failed"
NOTIFICATION_SINK_REGISTERED: Final[str] = "notification.sink.registered"
NOTIFICATION_CONSOLE_DELIVERED: Final[str] = "notification.console.delivered"
NOTIFICATION_NTFY_DELIVERED: Final[str] = "notification.ntfy.delivered"
NOTIFICATION_NTFY_FAILED: Final[str] = "notification.ntfy.failed"
NOTIFICATION_SLACK_DELIVERED: Final[str] = "notification.slack.delivered"
NOTIFICATION_SLACK_FAILED: Final[str] = "notification.slack.failed"
NOTIFICATION_EMAIL_DELIVERED: Final[str] = "notification.email.delivered"
NOTIFICATION_EMAIL_FAILED: Final[str] = "notification.email.failed"
NOTIFICATION_FILTERED: Final[str] = "notification.filtered"
NOTIFICATION_SINK_CONFIG_INVALID: Final[str] = "notification.sink.config_invalid"
NOTIFICATION_SINK_UNKNOWN_TYPE: Final[str] = "notification.sink.unknown_type"
NOTIFICATION_SINK_DISABLED: Final[str] = "notification.sink.disabled"
NOTIFICATION_NO_SINKS: Final[str] = "notification.no_sinks"
NOTIFICATION_EMAIL_PARTIAL_CREDENTIALS: Final[str] = (
    "notification.email.partial_credentials"
)
