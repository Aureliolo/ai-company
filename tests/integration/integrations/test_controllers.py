"""Controller-level integration tests for the 6 new integration APIs.

Covers:
- ``ConnectionsController`` -- list/get/create/update/delete/health
- ``OAuthController`` -- initiate, callback, status
- ``WebhooksController`` -- receive (signature verify, replay, bus publish)
- ``IntegrationHealthController`` -- aggregate + single
- ``MCPCatalogController`` -- browse/search/get
- ``TunnelController`` -- start/stop/status

Litestar wraps route handler methods in ``HTTPRouteHandler`` so we
invoke the underlying function via ``handler.fn(ctrl, ...)`` to
exercise them directly without spinning up the app.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from synthorg.api.errors import (
    ApiValidationError,
    ConflictError,
    NotFoundError,
    UnauthorizedError,
)
from synthorg.core.types import NotBlankStr
from synthorg.integrations.connections.models import (
    AuthMethod,
    Connection,
    ConnectionStatus,
    ConnectionType,
    HealthReport,
)
from synthorg.integrations.errors import (
    DuplicateConnectionError,
)


def _make_conn(name: str = "c1") -> Connection:
    return Connection(
        name=NotBlankStr(name),
        connection_type=ConnectionType.GITHUB,
        auth_method=AuthMethod.API_KEY,
        base_url=NotBlankStr("https://api.github.com"),
    )


@pytest.mark.integration
class TestConnectionsController:
    async def test_list_returns_catalog_entries(self) -> None:
        from synthorg.api.controllers.connections import ConnectionsController

        catalog = MagicMock()
        catalog.list_all = AsyncMock(return_value=(_make_conn("a"), _make_conn("b")))
        state = {"app_state": MagicMock(connection_catalog=catalog)}

        ctrl = ConnectionsController(owner=ConnectionsController)  # type: ignore[arg-type]
        response = await ctrl.list_connections.fn(ctrl, state=state)
        assert len(response.data) == 2

    async def test_get_missing_raises_not_found(self) -> None:
        from synthorg.api.controllers.connections import ConnectionsController

        catalog = MagicMock()
        catalog.get = AsyncMock(return_value=None)
        state = {"app_state": MagicMock(connection_catalog=catalog)}

        ctrl = ConnectionsController(owner=ConnectionsController)  # type: ignore[arg-type]
        with pytest.raises(NotFoundError):
            await ctrl.get_connection.fn(ctrl, state=state, name="missing")

    async def test_create_validates_missing_name(self) -> None:
        from synthorg.api.controllers.connections import ConnectionsController

        catalog = MagicMock()
        state = {"app_state": MagicMock(connection_catalog=catalog)}

        ctrl = ConnectionsController(owner=ConnectionsController)  # type: ignore[arg-type]
        with pytest.raises(ApiValidationError):
            await ctrl.create_connection.fn(
                ctrl,
                state=state,
                data={"connection_type": "github"},
            )

    async def test_create_validates_bad_connection_type(self) -> None:
        from synthorg.api.controllers.connections import ConnectionsController

        catalog = MagicMock()
        state = {"app_state": MagicMock(connection_catalog=catalog)}

        ctrl = ConnectionsController(owner=ConnectionsController)  # type: ignore[arg-type]
        with pytest.raises(ApiValidationError):
            await ctrl.create_connection.fn(
                ctrl,
                state=state,
                data={"name": "x", "connection_type": "not-a-type"},
            )

    async def test_create_duplicate_raises_conflict(self) -> None:
        from synthorg.api.controllers.connections import ConnectionsController

        catalog = MagicMock()
        catalog.create = AsyncMock(
            side_effect=DuplicateConnectionError("dup"),
        )
        state = {"app_state": MagicMock(connection_catalog=catalog)}

        ctrl = ConnectionsController(owner=ConnectionsController)  # type: ignore[arg-type]
        with pytest.raises(ConflictError):
            await ctrl.create_connection.fn(
                ctrl,
                state=state,
                data={
                    "name": "x",
                    "connection_type": "github",
                    "credentials": {"token": "t"},
                },
            )


@pytest.mark.integration
class TestWebhooksController:
    async def test_missing_signing_secret_fails_closed(self) -> None:
        from synthorg.api.controllers.webhooks import WebhooksController

        catalog = MagicMock()
        catalog.get = AsyncMock(return_value=_make_conn())
        catalog.get_credentials = AsyncMock(return_value={})

        state = {
            "app_state": MagicMock(
                connection_catalog=catalog,
                message_bus=MagicMock(),
            ),
        }

        request = MagicMock()
        request.body = AsyncMock(return_value=b"{}")
        request.headers = {}

        ctrl = WebhooksController(owner=WebhooksController)  # type: ignore[arg-type]
        with pytest.raises(UnauthorizedError):
            await ctrl.receive_webhook.fn(
                ctrl,
                state=state,
                request=request,
                connection_name="c1",
                event_type="ping",
            )

    async def test_malformed_timestamp_raises_validation(self) -> None:
        import hashlib
        import hmac

        from synthorg.api.controllers.webhooks import WebhooksController

        # Use generic_http so the generic HMAC verifier kicks in.
        conn = Connection(
            name=NotBlankStr("c1"),
            connection_type=ConnectionType.GENERIC_HTTP,
            auth_method=AuthMethod.API_KEY,
            base_url=NotBlankStr("https://example.com"),
        )
        catalog = MagicMock()
        catalog.get = AsyncMock(return_value=conn)
        catalog.get_credentials = AsyncMock(
            return_value={"signing_secret": "supersecret"},
        )

        state = {
            "app_state": MagicMock(
                connection_catalog=catalog,
                message_bus=MagicMock(),
            ),
        }

        body = b'{"hello":1}'
        secret = "supersecret"
        sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        request = MagicMock()
        request.body = AsyncMock(return_value=body)
        request.headers = {
            "X-Signature": sig,
            "X-Timestamp": "not-a-number",
        }

        ctrl = WebhooksController(owner=WebhooksController)  # type: ignore[arg-type]
        with pytest.raises(ApiValidationError):
            await ctrl.receive_webhook.fn(
                ctrl,
                state=state,
                request=request,
                connection_name="c1",
                event_type="push",
            )


@pytest.mark.integration
class TestIntegrationHealthController:
    async def test_aggregate_runs_checks_in_parallel(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from synthorg.api.controllers.integration_health import (
            IntegrationHealthController,
        )
        from synthorg.integrations.health import service as health_service

        conn1 = _make_conn("c1")
        conn2 = _make_conn("c2")

        catalog = MagicMock()
        catalog.list_all = AsyncMock(return_value=(conn1, conn2))
        catalog.get_or_raise = AsyncMock(
            side_effect=lambda name: conn1 if name == "c1" else conn2
        )

        async def fake_check(
            _catalog: object,
            name: str,
        ) -> HealthReport:
            return HealthReport(
                connection_name=NotBlankStr(name),
                status=ConnectionStatus.HEALTHY,
                latency_ms=1.0,
                checked_at=datetime.now(UTC),
            )

        # Patch the source module so the controller's import reference
        # picks up the fake. Patching via ``monkeypatch`` guarantees
        # the original is restored even if the test aborts.
        monkeypatch.setattr(health_service, "check_connection_health", fake_check)
        import synthorg.api.controllers.integration_health as controller_mod

        monkeypatch.setattr(controller_mod, "check_connection_health", fake_check)

        state = {"app_state": MagicMock(connection_catalog=catalog)}
        ctrl = IntegrationHealthController(owner=IntegrationHealthController)  # type: ignore[arg-type]
        response = await ctrl.aggregate_health.fn(ctrl, state=state)

        assert len(response.data) == 2
        assert {r.connection_name for r in response.data} == {"c1", "c2"}


@pytest.mark.integration
class TestMCPCatalogController:
    async def test_browse_returns_bundled_entries(self) -> None:
        from synthorg.api.controllers.mcp_catalog import MCPCatalogController
        from synthorg.integrations.mcp_catalog.service import CatalogService

        state = {"app_state": MagicMock(mcp_catalog_service=CatalogService())}
        ctrl = MCPCatalogController(owner=MCPCatalogController)  # type: ignore[arg-type]
        response = await ctrl.browse_catalog.fn(ctrl, state=state)
        assert len(response.data) >= 8


@pytest.mark.integration
class TestTunnelController:
    async def test_start_returns_public_url(self) -> None:
        from synthorg.api.controllers.tunnel import TunnelController

        tunnel = MagicMock()
        tunnel.start = AsyncMock(return_value="https://tunnel.example.com")
        state = {"app_state": MagicMock(tunnel_provider=tunnel)}
        ctrl = TunnelController(owner=TunnelController)  # type: ignore[arg-type]
        response = await ctrl.start_tunnel.fn(ctrl, state=state)
        assert response.data == {"public_url": "https://tunnel.example.com"}

    async def test_status_returns_current_url(self) -> None:
        from synthorg.api.controllers.tunnel import TunnelController

        tunnel = MagicMock()
        tunnel.get_url = AsyncMock(return_value="https://tunnel.example.com")
        state = {"app_state": MagicMock(tunnel_provider=tunnel)}
        ctrl = TunnelController(owner=TunnelController)  # type: ignore[arg-type]
        response = await ctrl.get_status.fn(ctrl, state=state)
        assert response.data == {"public_url": "https://tunnel.example.com"}


@pytest.mark.integration
class TestOAuthController:
    async def test_initiate_requires_connection_name(self) -> None:
        from synthorg.api.controllers.oauth import OAuthController

        ctrl = OAuthController(owner=OAuthController)  # type: ignore[arg-type]
        state = {"app_state": MagicMock()}
        with pytest.raises(ApiValidationError):
            await ctrl.initiate_flow.fn(ctrl, state=state, data={})

    async def test_status_returns_false_when_no_token(self) -> None:
        from synthorg.api.controllers.oauth import OAuthController

        conn = _make_conn()
        catalog = MagicMock()
        catalog.get_or_raise = AsyncMock(return_value=conn)
        catalog.get_credentials = AsyncMock(return_value={})
        state = {"app_state": MagicMock(connection_catalog=catalog)}

        ctrl = OAuthController(owner=OAuthController)  # type: ignore[arg-type]
        response = await ctrl.token_status.fn(
            ctrl,
            state=state,
            connection_name="c1",
        )
        assert response.data["has_token"] is False
