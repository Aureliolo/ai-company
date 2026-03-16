"""Tests for WsTicketStore."""

from unittest.mock import patch

import pytest

from synthorg.api.auth.models import AuthenticatedUser, AuthMethod
from synthorg.api.auth.ticket_store import WsTicketStore
from synthorg.api.guards import HumanRole


def _make_user(
    *,
    user_id: str = "test-user-001",
    username: str = "testadmin",
    role: HumanRole = HumanRole.CEO,
) -> AuthenticatedUser:
    return AuthenticatedUser(
        user_id=user_id,
        username=username,
        role=role,
        auth_method=AuthMethod.WS_TICKET,
    )


class TestWsTicketStoreCreate:
    """Tests for ticket creation."""

    @pytest.mark.unit
    def test_create_returns_url_safe_string(self) -> None:
        store = WsTicketStore()
        user = _make_user()
        ticket = store.create(user)

        assert isinstance(ticket, str)
        assert len(ticket) > 0
        # URL-safe base64 characters only
        import re

        assert re.fullmatch(r"[A-Za-z0-9_-]+", ticket)

    @pytest.mark.unit
    def test_create_returns_unique_tickets(self) -> None:
        store = WsTicketStore()
        user = _make_user()
        tickets = {store.create(user) for _ in range(100)}
        assert len(tickets) == 100

    @pytest.mark.unit
    def test_ttl_seconds_property(self) -> None:
        store = WsTicketStore(ttl_seconds=60.0)
        assert store.ttl_seconds == 60.0

    @pytest.mark.unit
    def test_zero_ttl_rejected(self) -> None:
        with pytest.raises(ValueError, match="positive"):
            WsTicketStore(ttl_seconds=0.0)

    @pytest.mark.unit
    def test_negative_ttl_rejected(self) -> None:
        with pytest.raises(ValueError, match="positive"):
            WsTicketStore(ttl_seconds=-5.0)


class TestWsTicketStoreValidateAndConsume:
    """Tests for ticket validation and consumption."""

    @pytest.mark.unit
    def test_validate_and_consume_returns_user(self) -> None:
        store = WsTicketStore()
        user = _make_user()
        ticket = store.create(user)

        result = store.validate_and_consume(ticket)

        assert result is not None
        assert result.user_id == user.user_id
        assert result.username == user.username
        assert result.role == user.role
        assert result.auth_method == AuthMethod.WS_TICKET

    @pytest.mark.unit
    def test_validate_and_consume_single_use(self) -> None:
        store = WsTicketStore()
        user = _make_user()
        ticket = store.create(user)

        first = store.validate_and_consume(ticket)
        second = store.validate_and_consume(ticket)

        assert first is not None
        assert second is None

    @pytest.mark.unit
    def test_validate_and_consume_expired(self) -> None:
        store = WsTicketStore(ttl_seconds=10.0)
        user = _make_user()

        base_time = 1000.0
        with patch(
            "synthorg.api.auth.ticket_store.time.monotonic", return_value=base_time
        ):
            ticket = store.create(user)

        # Advance past expiry
        with patch(
            "synthorg.api.auth.ticket_store.time.monotonic",
            return_value=base_time + 11.0,
        ):
            result = store.validate_and_consume(ticket)

        assert result is None

    @pytest.mark.unit
    def test_validate_and_consume_just_before_expiry(self) -> None:
        store = WsTicketStore(ttl_seconds=10.0)
        user = _make_user()

        base_time = 1000.0
        with patch(
            "synthorg.api.auth.ticket_store.time.monotonic", return_value=base_time
        ):
            ticket = store.create(user)

        # Just before expiry — should still work
        with patch(
            "synthorg.api.auth.ticket_store.time.monotonic",
            return_value=base_time + 9.9,
        ):
            result = store.validate_and_consume(ticket)

        assert result is not None

    @pytest.mark.unit
    def test_validate_and_consume_unknown_ticket(self) -> None:
        store = WsTicketStore()
        result = store.validate_and_consume("nonexistent-ticket")
        assert result is None

    @pytest.mark.unit
    def test_validate_and_consume_empty_string(self) -> None:
        store = WsTicketStore()
        result = store.validate_and_consume("")
        assert result is None

    @pytest.mark.unit
    def test_custom_ttl(self) -> None:
        store = WsTicketStore(ttl_seconds=5.0)
        user = _make_user()

        base_time = 1000.0
        with patch(
            "synthorg.api.auth.ticket_store.time.monotonic", return_value=base_time
        ):
            ticket = store.create(user)

        # Within custom TTL
        with patch(
            "synthorg.api.auth.ticket_store.time.monotonic",
            return_value=base_time + 4.0,
        ):
            result = store.validate_and_consume(ticket)
        assert result is not None

    @pytest.mark.unit
    def test_custom_ttl_expired(self) -> None:
        store = WsTicketStore(ttl_seconds=5.0)
        user = _make_user()

        base_time = 1000.0
        with patch(
            "synthorg.api.auth.ticket_store.time.monotonic", return_value=base_time
        ):
            ticket = store.create(user)

        # Past custom TTL
        with patch(
            "synthorg.api.auth.ticket_store.time.monotonic",
            return_value=base_time + 6.0,
        ):
            result = store.validate_and_consume(ticket)
        assert result is None


class TestWsTicketStoreCleanup:
    """Tests for expired ticket cleanup."""

    @pytest.mark.unit
    def test_cleanup_expired_removes_old_entries(self) -> None:
        store = WsTicketStore(ttl_seconds=10.0)
        user = _make_user()

        base_time = 1000.0
        with patch(
            "synthorg.api.auth.ticket_store.time.monotonic", return_value=base_time
        ):
            store.create(user)
            store.create(user)

        with patch(
            "synthorg.api.auth.ticket_store.time.monotonic",
            return_value=base_time + 11.0,
        ):
            removed = store.cleanup_expired()

        assert removed == 2

    @pytest.mark.unit
    def test_cleanup_preserves_valid_entries(self) -> None:
        store = WsTicketStore(ttl_seconds=10.0)
        user = _make_user()

        base_time = 1000.0
        with patch(
            "synthorg.api.auth.ticket_store.time.monotonic", return_value=base_time
        ):
            ticket = store.create(user)

        # Still within TTL
        with patch(
            "synthorg.api.auth.ticket_store.time.monotonic",
            return_value=base_time + 5.0,
        ):
            removed = store.cleanup_expired()

        assert removed == 0
        # Ticket should still be valid
        with patch(
            "synthorg.api.auth.ticket_store.time.monotonic",
            return_value=base_time + 5.0,
        ):
            result = store.validate_and_consume(ticket)
        assert result is not None

    @pytest.mark.unit
    def test_cleanup_mixed_expired_and_valid(self) -> None:
        store = WsTicketStore(ttl_seconds=10.0)
        user = _make_user()

        base_time = 1000.0
        # Create two tickets at different times
        with patch(
            "synthorg.api.auth.ticket_store.time.monotonic", return_value=base_time
        ):
            store.create(user)  # expires at 1010

        with patch(
            "synthorg.api.auth.ticket_store.time.monotonic",
            return_value=base_time + 8.0,
        ):
            valid_ticket = store.create(user)  # expires at 1018

        # At t=1012: first expired, second still valid
        with patch(
            "synthorg.api.auth.ticket_store.time.monotonic",
            return_value=base_time + 12.0,
        ):
            removed = store.cleanup_expired()

        assert removed == 1
        with patch(
            "synthorg.api.auth.ticket_store.time.monotonic",
            return_value=base_time + 12.0,
        ):
            result = store.validate_and_consume(valid_ticket)
        assert result is not None

    @pytest.mark.unit
    def test_cleanup_empty_store(self) -> None:
        store = WsTicketStore()
        removed = store.cleanup_expired()
        assert removed == 0
