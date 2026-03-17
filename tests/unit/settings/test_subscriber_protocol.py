"""Tests for SettingsSubscriber protocol."""

import pytest

from synthorg.settings.subscriber import SettingsSubscriber


class _ConformingSubscriber:
    """Minimal class that satisfies the SettingsSubscriber protocol."""

    @property
    def watched_keys(self) -> frozenset[tuple[str, str]]:
        return frozenset({("ns", "key")})

    @property
    def subscriber_name(self) -> str:
        return "test-subscriber"

    async def on_settings_changed(
        self,
        namespace: str,
        key: str,
    ) -> None:
        pass


class _MissingMethod:
    """Missing on_settings_changed method."""

    @property
    def watched_keys(self) -> frozenset[tuple[str, str]]:
        return frozenset()

    @property
    def subscriber_name(self) -> str:
        return "broken"


@pytest.mark.unit
class TestSettingsSubscriberProtocol:
    """SettingsSubscriber protocol conformance."""

    def test_runtime_checkable(self) -> None:
        """Protocol is runtime-checkable via isinstance."""
        sub = _ConformingSubscriber()
        assert isinstance(sub, SettingsSubscriber)

    def test_non_conforming_fails_isinstance(self) -> None:
        """Class missing on_settings_changed is not a subscriber."""
        broken = _MissingMethod()
        assert not isinstance(broken, SettingsSubscriber)

    def test_watched_keys_returns_frozenset(self) -> None:
        """watched_keys returns a frozenset of (namespace, key) tuples."""
        sub = _ConformingSubscriber()
        keys = sub.watched_keys
        assert isinstance(keys, frozenset)
        assert ("ns", "key") in keys

    def test_subscriber_name(self) -> None:
        """subscriber_name returns a string."""
        sub = _ConformingSubscriber()
        assert sub.subscriber_name == "test-subscriber"

    async def test_on_settings_changed_is_async(self) -> None:
        """on_settings_changed is awaitable."""
        sub = _ConformingSubscriber()
        # Should not raise
        await sub.on_settings_changed("ns", "key")
