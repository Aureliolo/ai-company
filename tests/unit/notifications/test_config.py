"""Tests for notification configuration models."""

import pytest
from pydantic import ValidationError

from synthorg.notifications.config import (
    NotificationConfig,
    NotificationSinkConfig,
)
from synthorg.notifications.models import NotificationSeverity


@pytest.mark.unit
class TestNotificationSinkConfig:
    def test_defaults(self) -> None:
        cfg = NotificationSinkConfig(type="console")
        assert cfg.type == "console"
        assert cfg.enabled is True
        assert cfg.params == {}

    def test_custom(self) -> None:
        cfg = NotificationSinkConfig(
            type="ntfy",
            params={"server_url": "https://ntfy.sh", "topic": "test"},
        )
        assert cfg.type == "ntfy"
        assert cfg.params["topic"] == "test"

    def test_frozen(self) -> None:
        cfg = NotificationSinkConfig(type="console")
        with pytest.raises(ValidationError):
            cfg.type = "other"  # type: ignore[misc]


@pytest.mark.unit
class TestNotificationConfig:
    def test_defaults(self) -> None:
        cfg = NotificationConfig()
        assert len(cfg.sinks) == 1
        assert cfg.sinks[0].type == "console"
        assert cfg.min_severity == NotificationSeverity.INFO

    def test_custom_sinks(self) -> None:
        cfg = NotificationConfig(
            sinks=(
                NotificationSinkConfig(type="ntfy", params={"topic": "t"}),
                NotificationSinkConfig(type="slack", enabled=False),
            ),
            min_severity=NotificationSeverity.WARNING,
        )
        assert len(cfg.sinks) == 2
        assert cfg.min_severity == NotificationSeverity.WARNING

    def test_frozen(self) -> None:
        cfg = NotificationConfig()
        with pytest.raises(ValidationError):
            cfg.min_severity = NotificationSeverity.ERROR  # type: ignore[misc]
