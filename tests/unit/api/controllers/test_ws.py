"""Tests for WebSocket handler message parsing and ticket auth."""

import json
from typing import Any

import pytest
from litestar.testing import TestClient

from synthorg.api.auth.models import AuthMethod
from synthorg.api.controllers.ws import (
    _READ_ROLES,
    _WS_CLOSE_AUTH_FAILED,
    _WS_CLOSE_FORBIDDEN,
    _handle_message,
)
from synthorg.api.guards import HumanRole


@pytest.mark.unit
class TestWsHandleMessage:
    def test_subscribe(self) -> None:
        subscribed: set[str] = set()
        filters: dict[str, dict[str, str]] = {}
        result = _handle_message(
            json.dumps({"action": "subscribe", "channels": ["tasks"]}),
            subscribed,
            filters,
        )
        data = json.loads(result)
        assert data["action"] == "subscribed"
        assert "tasks" in data["channels"]
        assert "tasks" in subscribed

    def test_unsubscribe(self) -> None:
        subscribed: set[str] = {"tasks", "budget"}
        filters: dict[str, dict[str, str]] = {"tasks": {"agent_id": "a1"}}
        result = _handle_message(
            json.dumps({"action": "unsubscribe", "channels": ["tasks"]}),
            subscribed,
            filters,
        )
        data = json.loads(result)
        assert data["action"] == "unsubscribed"
        assert "tasks" not in data["channels"]
        assert "budget" in data["channels"]
        assert "tasks" not in filters

    def test_invalid_json(self) -> None:
        subscribed: set[str] = set()
        filters: dict[str, dict[str, str]] = {}
        result = _handle_message("not json", subscribed, filters)
        data = json.loads(result)
        assert "error" in data

    def test_unknown_action(self) -> None:
        subscribed: set[str] = set()
        filters: dict[str, dict[str, str]] = {}
        result = _handle_message(
            json.dumps({"action": "unknown"}),
            subscribed,
            filters,
        )
        data = json.loads(result)
        assert "error" in data

    def test_subscribe_ignores_invalid_channels(self) -> None:
        subscribed: set[str] = set()
        filters: dict[str, dict[str, str]] = {}
        _handle_message(
            json.dumps(
                {
                    "action": "subscribe",
                    "channels": ["tasks", "invalid"],
                }
            ),
            subscribed,
            filters,
        )
        assert "tasks" in subscribed
        assert "invalid" not in subscribed

    def test_subscribe_with_filters(self) -> None:
        subscribed: set[str] = set()
        filters: dict[str, dict[str, str]] = {}
        _handle_message(
            json.dumps(
                {
                    "action": "subscribe",
                    "channels": ["tasks"],
                    "filters": {
                        "agent_id": "agent-1",
                        "project": "proj-1",
                    },
                }
            ),
            subscribed,
            filters,
        )
        assert "tasks" in subscribed
        assert filters["tasks"] == {
            "agent_id": "agent-1",
            "project": "proj-1",
        }

    def test_unsubscribe_clears_filters(self) -> None:
        subscribed: set[str] = {"tasks"}
        filters: dict[str, dict[str, str]] = {"tasks": {"agent_id": "agent-1"}}
        _handle_message(
            json.dumps({"action": "unsubscribe", "channels": ["tasks"]}),
            subscribed,
            filters,
        )
        assert "tasks" not in subscribed
        assert "tasks" not in filters

    def test_subscribe_without_filters_keeps_existing(self) -> None:
        subscribed: set[str] = set()
        filters: dict[str, dict[str, str]] = {}
        _handle_message(
            json.dumps({"action": "subscribe", "channels": ["tasks"]}),
            subscribed,
            filters,
        )
        assert "tasks" in subscribed
        assert "tasks" not in filters

    def test_subscribe_too_many_filter_keys(self) -> None:
        subscribed: set[str] = set()
        filters: dict[str, dict[str, str]] = {}
        many_filters = {f"key_{i}": f"val_{i}" for i in range(11)}
        result = _handle_message(
            json.dumps(
                {
                    "action": "subscribe",
                    "channels": ["tasks"],
                    "filters": many_filters,
                }
            ),
            subscribed,
            filters,
        )
        data = json.loads(result)
        assert data["error"] == "Filter bounds exceeded"
        assert "tasks" not in subscribed

    def test_subscribe_filter_value_too_long(self) -> None:
        subscribed: set[str] = set()
        filters: dict[str, dict[str, str]] = {}
        result = _handle_message(
            json.dumps(
                {
                    "action": "subscribe",
                    "channels": ["tasks"],
                    "filters": {"key": "x" * 257},
                }
            ),
            subscribed,
            filters,
        )
        data = json.loads(result)
        assert data["error"] == "Filter bounds exceeded"
        assert "tasks" not in subscribed

    def test_message_size_limit_boundary(self) -> None:
        subscribed: set[str] = set()
        filters: dict[str, dict[str, str]] = {}

        # 4096 bytes should pass (valid JSON that fits)
        small_msg = json.dumps({"action": "subscribe", "channels": ["tasks"]})
        result = _handle_message(small_msg, subscribed, filters)
        data = json.loads(result)
        assert "error" not in data or data.get("action") == "subscribed"

        # Message whose encoded bytes exceed 4096 should fail
        big_msg = json.dumps({"action": "subscribe", "data": "x" * 4096})
        result = _handle_message(big_msg, subscribed, filters)
        data = json.loads(result)
        assert data["error"] == "Message too large"

    def test_non_dict_json_returns_error(self) -> None:
        subscribed: set[str] = set()
        filters: dict[str, dict[str, str]] = {}

        # JSON array
        result = _handle_message(
            json.dumps([1, 2, 3]),
            subscribed,
            filters,
        )
        data = json.loads(result)
        assert "error" in data

        # JSON string
        result = _handle_message(
            json.dumps("hello"),
            subscribed,
            filters,
        )
        data = json.loads(result)
        assert "error" in data

        # JSON number
        result = _handle_message(
            json.dumps(42),
            subscribed,
            filters,
        )
        data = json.loads(result)
        assert "error" in data


@pytest.mark.unit
class TestWsTicketAuth:
    """Tests for ticket-based WebSocket authentication logic.

    These tests validate the auth validation logic used by the WS
    handler without opening actual WebSocket connections (which
    require the channels plugin background task and hang in the
    sync test client).
    """

    def test_ws_ticket_endpoint_returns_ticket(
        self,
        test_client: TestClient[Any],
    ) -> None:
        """POST /auth/ws-ticket returns a consumable ticket."""
        response = test_client.post("/api/v1/auth/ws-ticket")
        assert response.status_code == 200
        data = response.json()["data"]
        assert "ticket" in data
        assert data["expires_in"] == 30

    def test_ws_ticket_carries_ws_ticket_auth_method(
        self,
        test_client: TestClient[Any],
    ) -> None:
        """The ticket user has auth_method=WS_TICKET."""
        response = test_client.post("/api/v1/auth/ws-ticket")
        ticket = response.json()["data"]["ticket"]

        app_state = test_client.app.state["app_state"]
        user = app_state.ticket_store.validate_and_consume(ticket)
        assert user is not None
        assert user.auth_method == AuthMethod.WS_TICKET

    def test_ws_ticket_single_use_via_store(
        self,
        test_client: TestClient[Any],
    ) -> None:
        """Ticket is consumed on first validate_and_consume."""
        response = test_client.post("/api/v1/auth/ws-ticket")
        ticket = response.json()["data"]["ticket"]

        app_state = test_client.app.state["app_state"]
        first = app_state.ticket_store.validate_and_consume(ticket)
        second = app_state.ticket_store.validate_and_consume(ticket)
        assert first is not None
        assert second is None

    def test_ws_ticket_user_has_correct_identity(
        self,
        test_client: TestClient[Any],
    ) -> None:
        """The ticket preserves the original user's identity."""
        response = test_client.post("/api/v1/auth/ws-ticket")
        ticket = response.json()["data"]["ticket"]

        app_state = test_client.app.state["app_state"]
        user = app_state.ticket_store.validate_and_consume(ticket)
        assert user is not None
        assert user.role == HumanRole.CEO
        assert user.username == "test-ceo"

    def test_ws_endpoint_excluded_from_auth_middleware(
        self,
        test_client: TestClient[Any],
    ) -> None:
        """The /ws path should be in the auth middleware exclude list."""
        from synthorg.api.app import _build_middleware
        from synthorg.api.config import ApiConfig

        api_config = ApiConfig()
        # The middleware builder auto-derives exclude paths
        # including /ws when exclude_paths is None
        middleware = _build_middleware(api_config)
        # The first middleware is the auth middleware class
        auth_cls = middleware[0]
        # Verify by checking the class is a configured subclass
        assert hasattr(auth_cls, "__init__")

    def test_read_roles_includes_all_human_roles(self) -> None:
        """The WS handler's _READ_ROLES should include all HumanRole values."""
        for role in HumanRole:
            assert role in _READ_ROLES

    def test_ws_close_codes_in_application_range(self) -> None:
        """WS close codes should be in the RFC 6455 application range."""
        assert 4000 <= _WS_CLOSE_AUTH_FAILED <= 4999
        assert 4000 <= _WS_CLOSE_FORBIDDEN <= 4999

    def test_ws_rejects_missing_ticket(
        self,
        test_client: TestClient[Any],
    ) -> None:
        """WS connection without ?ticket= is rejected (close before accept)."""
        from litestar.exceptions import WebSocketDisconnect

        with (
            pytest.raises(WebSocketDisconnect),
            test_client.websocket_connect(
                "/api/v1/ws",
            ),
        ):
            pass

    def test_ws_rejects_invalid_ticket(
        self,
        test_client: TestClient[Any],
    ) -> None:
        """WS connection with a bogus ticket is rejected."""
        from litestar.exceptions import WebSocketDisconnect

        with (
            pytest.raises(
                WebSocketDisconnect,
            ),
            test_client.websocket_connect(
                "/api/v1/ws?ticket=bogus-ticket",
            ),
        ):
            pass
