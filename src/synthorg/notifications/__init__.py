"""Notification subsystem for operator alerts.

Provides a pluggable ``NotificationSink`` protocol with adapters
for ntfy, Slack, email, and console logging. The
``NotificationDispatcher`` fans out notifications to all registered
sinks concurrently.
"""

from synthorg.notifications.config import (
    NotificationConfig,
    NotificationSinkConfig,
    NotificationSinkType,
)
from synthorg.notifications.dispatcher import NotificationDispatcher
from synthorg.notifications.factory import build_notification_dispatcher
from synthorg.notifications.models import (
    Notification,
    NotificationCategory,
    NotificationSeverity,
)
from synthorg.notifications.protocol import NotificationSink

__all__ = [
    "Notification",
    "NotificationCategory",
    "NotificationConfig",
    "NotificationDispatcher",
    "NotificationSeverity",
    "NotificationSink",
    "NotificationSinkConfig",
    "NotificationSinkType",
    "build_notification_dispatcher",
]
