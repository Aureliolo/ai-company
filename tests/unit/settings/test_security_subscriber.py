"""Tests for SecuritySubscriber."""

from unittest.mock import AsyncMock

import pytest

from synthorg.settings.subscribers.security_subscriber import (
    SecuritySubscriber,
)

pytestmark = pytest.mark.unit


class TestSecuritySubscriber:
    """Tests for SecuritySubscriber."""

    def test_watched_keys(self) -> None:
        sub = SecuritySubscriber(on_allowlist_changed=AsyncMock())
        assert ("security", "discovery_allowlist") in sub.watched_keys

    def test_subscriber_name(self) -> None:
        sub = SecuritySubscriber(on_allowlist_changed=AsyncMock())
        assert sub.subscriber_name == "security-discovery-allowlist"

    async def test_ignores_unrelated_keys(self) -> None:
        sub = SecuritySubscriber(on_allowlist_changed=AsyncMock())
        # Should not raise or call callback for unrelated keys
        await sub.on_settings_changed("security", "enabled")

    async def test_handles_discovery_allowlist_change(self) -> None:
        sub = SecuritySubscriber(on_allowlist_changed=AsyncMock())
        # Should not raise for the watched key
        await sub.on_settings_changed("security", "discovery_allowlist")
