"""Tests for BackupSettingsSubscriber."""

from unittest.mock import AsyncMock, MagicMock, PropertyMock

import pytest

from synthorg.settings.subscriber import SettingsSubscriber
from synthorg.settings.subscribers.backup_subscriber import (
    BackupSettingsSubscriber,
)


def _make_subscriber(
    *,
    scheduler_running: bool = False,
) -> tuple[BackupSettingsSubscriber, MagicMock]:
    """Create a subscriber with a mock BackupService.

    Args:
        scheduler_running: Initial ``is_running`` state of the mock scheduler.

    Returns:
        Tuple of (subscriber, mock_backup_service).
    """
    scheduler = MagicMock()
    type(scheduler).is_running = PropertyMock(return_value=scheduler_running)
    scheduler.start = MagicMock()
    scheduler.stop = AsyncMock()

    service = MagicMock()
    type(service).scheduler = PropertyMock(return_value=scheduler)

    sub = BackupSettingsSubscriber(backup_service=service)
    return sub, service


@pytest.mark.unit
class TestBackupSubscriberProtocol:
    """BackupSettingsSubscriber conforms to SettingsSubscriber."""

    def test_isinstance_check(self) -> None:
        sub, _ = _make_subscriber()
        assert isinstance(sub, SettingsSubscriber)

    def test_watched_keys_returns_expected_frozenset(self) -> None:
        sub, _ = _make_subscriber()
        expected = frozenset(
            {
                ("backup", "enabled"),
                ("backup", "schedule_hours"),
                ("backup", "compression"),
                ("backup", "on_shutdown"),
                ("backup", "on_startup"),
            }
        )
        assert sub.watched_keys == expected

    def test_subscriber_name(self) -> None:
        sub, _ = _make_subscriber()
        assert sub.subscriber_name == "backup-settings"


@pytest.mark.unit
class TestBackupSubscriberEnabled:
    """on_settings_changed('backup', 'enabled') toggles the scheduler."""

    async def test_enabled_starts_scheduler_when_stopped(self) -> None:
        sub, service = _make_subscriber(scheduler_running=False)

        await sub.on_settings_changed("backup", "enabled")

        service.scheduler.start.assert_called_once()
        service.scheduler.stop.assert_not_awaited()

    async def test_enabled_stops_scheduler_when_running(self) -> None:
        sub, service = _make_subscriber(scheduler_running=True)

        await sub.on_settings_changed("backup", "enabled")

        service.scheduler.stop.assert_awaited_once()
        service.scheduler.start.assert_not_called()

    async def test_enabled_toggle_is_idempotent(self) -> None:
        """Calling twice with same state does not error."""
        sub, service = _make_subscriber(scheduler_running=False)
        await sub.on_settings_changed("backup", "enabled")
        await sub.on_settings_changed("backup", "enabled")
        # Two start() calls -- no crash, idempotent
        assert service.scheduler.start.call_count == 2


@pytest.mark.unit
class TestBackupSubscriberAdvisory:
    """Advisory keys log info but do not touch the scheduler."""

    @pytest.mark.parametrize(
        "key",
        [
            "schedule_hours",
            "compression",
            "on_shutdown",
            "on_startup",
        ],
    )
    async def test_advisory_key_does_not_start_scheduler(
        self,
        key: str,
    ) -> None:
        sub, service = _make_subscriber(scheduler_running=False)

        await sub.on_settings_changed("backup", key)

        service.scheduler.start.assert_not_called()
        service.scheduler.stop.assert_not_awaited()

    async def test_schedule_hours_is_advisory(self) -> None:
        """schedule_hours logs a reschedule advisory but does not stop/start."""
        sub, service = _make_subscriber(scheduler_running=True)

        await sub.on_settings_changed("backup", "schedule_hours")

        service.scheduler.start.assert_not_called()
        service.scheduler.stop.assert_not_awaited()

    @pytest.mark.parametrize(
        "key",
        ["compression", "on_shutdown", "on_startup"],
    )
    async def test_advisory_keys_do_not_raise(self, key: str) -> None:
        sub, _ = _make_subscriber()
        # Should complete without error -- just logs INFO
        await sub.on_settings_changed("backup", key)
