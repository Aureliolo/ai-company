"""Tests for notification configuration models."""

import pytest
from pydantic import ValidationError

from synthorg.notifications.config import (
    NotificationConfig,
    NotificationSinkConfig,
    NotificationSinkType,
)
from synthorg.notifications.models import NotificationSeverity


@pytest.mark.unit
class TestNotificationSinkConfig:
    def test_defaults(self) -> None:
        cfg = NotificationSinkConfig(type=NotificationSinkType.CONSOLE)
        assert cfg.type == NotificationSinkType.CONSOLE
        assert cfg.enabled is True
        assert cfg.params == {}

    def test_custom(self) -> None:
        cfg = NotificationSinkConfig(
            type=NotificationSinkType.NTFY,
            params={"server_url": "https://ntfy.sh", "topic": "test"},
        )
        assert cfg.type == NotificationSinkType.NTFY
        assert cfg.params["topic"] == "test"

    def test_frozen(self) -> None:
        cfg = NotificationSinkConfig(type=NotificationSinkType.CONSOLE)
        with pytest.raises(ValidationError):
            cfg.type = NotificationSinkType.NTFY  # type: ignore[misc]

    def test_invalid_type_rejected(self) -> None:
        with pytest.raises(ValidationError):
            NotificationSinkConfig(type="invalid_sink")  # type: ignore[arg-type]


@pytest.mark.unit
class TestNotificationConfig:
    def test_defaults(self) -> None:
        cfg = NotificationConfig()
        assert len(cfg.sinks) == 1
        assert cfg.sinks[0].type == NotificationSinkType.CONSOLE
        assert cfg.min_severity == NotificationSeverity.INFO

    def test_custom_sinks(self) -> None:
        cfg = NotificationConfig(
            sinks=(
                NotificationSinkConfig(
                    type=NotificationSinkType.NTFY,
                    params={"topic": "t"},
                ),
                NotificationSinkConfig(
                    type=NotificationSinkType.SLACK,
                    enabled=False,
                ),
            ),
            min_severity=NotificationSeverity.WARNING,
        )
        assert len(cfg.sinks) == 2
        assert cfg.min_severity == NotificationSeverity.WARNING

    def test_frozen(self) -> None:
        cfg = NotificationConfig()
        with pytest.raises(ValidationError):
            cfg.min_severity = NotificationSeverity.ERROR  # type: ignore[misc]
