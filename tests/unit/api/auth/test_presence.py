"""Tests for user presence tracking."""

import pytest

from synthorg.api.auth.presence import UserPresence

pytestmark = pytest.mark.unit


class TestUserPresence:
    def test_initially_empty(self) -> None:
        p = UserPresence()
        assert p.online_users() == frozenset()
        assert p.is_online("u1") is False
        assert p.connection_count("u1") == 0

    def test_connect_makes_user_online(self) -> None:
        p = UserPresence()
        p.connect("u1")
        assert p.is_online("u1") is True
        assert p.connection_count("u1") == 1
        assert p.online_users() == frozenset({"u1"})

    def test_disconnect_makes_user_offline(self) -> None:
        p = UserPresence()
        p.connect("u1")
        p.disconnect("u1")
        assert p.is_online("u1") is False
        assert p.connection_count("u1") == 0
        assert p.online_users() == frozenset()

    def test_multi_tab_counting(self) -> None:
        p = UserPresence()
        p.connect("u1")
        p.connect("u1")
        p.connect("u1")
        assert p.connection_count("u1") == 3
        assert p.is_online("u1") is True

        p.disconnect("u1")
        assert p.connection_count("u1") == 2
        assert p.is_online("u1") is True

        p.disconnect("u1")
        p.disconnect("u1")
        assert p.is_online("u1") is False

    def test_multiple_users(self) -> None:
        p = UserPresence()
        p.connect("u1")
        p.connect("u2")
        p.connect("u3")
        assert p.online_users() == frozenset({"u1", "u2", "u3"})

        p.disconnect("u2")
        assert p.online_users() == frozenset({"u1", "u3"})

    def test_disconnect_without_connect_safe(self) -> None:
        p = UserPresence()
        p.disconnect("u1")  # Should not raise
        assert p.is_online("u1") is False
        assert p.connection_count("u1") == 0
