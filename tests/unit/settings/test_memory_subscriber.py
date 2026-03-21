"""Tests for MemorySettingsSubscriber."""

import pytest

from synthorg.settings.subscriber import SettingsSubscriber
from synthorg.settings.subscribers.memory_subscriber import (
    MemorySettingsSubscriber,
)


@pytest.mark.unit
class TestMemorySubscriberProtocol:
    """MemorySettingsSubscriber conforms to SettingsSubscriber."""

    def test_isinstance_check(self) -> None:
        sub = MemorySettingsSubscriber()
        assert isinstance(sub, SettingsSubscriber)

    def test_watched_keys(self) -> None:
        sub = MemorySettingsSubscriber()
        assert ("memory", "default_level") in sub.watched_keys
        assert ("memory", "consolidation_interval") in sub.watched_keys
        # memory/backend has restart_required=True -- filtered by
        # dispatcher, not watched by subscriber
        assert ("memory", "backend") not in sub.watched_keys

    def test_subscriber_name(self) -> None:
        sub = MemorySettingsSubscriber()
        assert sub.subscriber_name == "memory-settings"


@pytest.mark.unit
class TestMemorySubscriberBehavior:
    """on_settings_changed logs info (does not rebuild)."""

    async def test_on_settings_changed_does_not_raise(self) -> None:
        sub = MemorySettingsSubscriber()
        # Should not raise -- just logs INFO
        await sub.on_settings_changed("memory", "default_level")
        await sub.on_settings_changed("memory", "consolidation_interval")

    async def test_on_settings_changed_is_idempotent(self) -> None:
        sub = MemorySettingsSubscriber()
        await sub.on_settings_changed("memory", "default_level")
        await sub.on_settings_changed("memory", "default_level")
        # No side effects, no error
