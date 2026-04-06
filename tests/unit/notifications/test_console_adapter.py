"""Tests for the console notification sink."""

import pytest

from synthorg.notifications.adapters.console import ConsoleNotificationSink
from synthorg.notifications.models import (
    Notification,
    NotificationCategory,
    NotificationSeverity,
)


@pytest.mark.unit
class TestConsoleNotificationSink:
    def test_sink_name(self) -> None:
        sink = ConsoleNotificationSink()
        assert sink.sink_name == "console"

    async def test_send_does_not_raise(self) -> None:
        sink = ConsoleNotificationSink()
        n = Notification(
            category=NotificationCategory.SYSTEM,
            severity=NotificationSeverity.ERROR,
            title="Test error",
            source="test",
        )
        await sink.send(n)
