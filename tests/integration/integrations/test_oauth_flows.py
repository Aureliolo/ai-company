"""Integration tests for all three OAuth 2.1 flows.

- Authorization code + PKCE (with callback handler storing tokens)
- Device flow (RFC 8628) including ``authorization_pending`` polling
- Client credentials (M2M)

These tests mock ``httpx.AsyncClient`` to avoid real network calls.
They exercise the actual flow classes end-to-end and verify that
raw tokens are returned (not placeholder ``pending-*`` refs).
"""

from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from synthorg.core.types import NotBlankStr
from synthorg.integrations.connections.models import (
    AuthMethod,
    Connection,
    ConnectionType,
    OAuthState,
)
from synthorg.integrations.errors import (
    InvalidStateError,
    TokenExchangeFailedError,
)
from synthorg.integrations.oauth.callback_handler import handle_oauth_callback
from synthorg.integrations.oauth.flows.authorization_code import (
    AuthorizationCodeFlow,
)
from synthorg.integrations.oauth.flows.client_credentials import (
    ClientCredentialsFlow,
)
from synthorg.integrations.oauth.flows.device_flow import DeviceFlow
from synthorg.integrations.oauth.pkce import (
    encrypt_pkce_verifier,
    generate_code_verifier,
)


def _mock_token_response(
    json_body: dict[str, Any],
    status_code: int = 200,
) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_body
    resp.raise_for_status = MagicMock()
    resp.is_error = status_code >= 400
    return resp


@pytest.mark.integration
class TestAuthorizationCodeFlow:
    async def test_exchange_code_returns_raw_tokens(self) -> None:
        flow = AuthorizationCodeFlow()
        # OAuthState now stores the PKCE verifier encrypted at rest;
        # build the same ciphertext the real ``start_flow`` would
        # produce so ``exchange_code`` can decrypt it back.
        verifier = generate_code_verifier()
        state = OAuthState(
            state_token=NotBlankStr("state-xyz"),
            connection_name=NotBlankStr("conn-1"),
            pkce_verifier=NotBlankStr(encrypt_pkce_verifier(verifier)),
            scopes_requested="read",
            redirect_uri="https://app.example.com/cb",
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
        resp = _mock_token_response(
            {
                "access_token": "atk-123",
                "refresh_token": "rtk-456",
                "token_type": "Bearer",
                "expires_in": 3600,
                "scope": "read",
            }
        )
        client_mock = AsyncMock()
        client_mock.post.return_value = resp

        async def _enter(self: Any) -> AsyncMock:
            return client_mock

        async def _exit(self: Any, *_: Any) -> None:
            return None

        with patch(
            "synthorg.integrations.oauth.flows.authorization_code.httpx.AsyncClient"
        ) as client_cls:
            client_cls.return_value.__aenter__ = _enter
            client_cls.return_value.__aexit__ = _exit
            token = await flow.exchange_code(
                token_url="https://example.com/token",
                client_id="cid",
                client_secret="csec",
                state=state,
                code="auth-code",
                redirect_uri="https://app.example.com/cb",
            )
        assert token.access_token == "atk-123"
        assert token.refresh_token == "rtk-456"
        assert token.token_type == "Bearer"
        assert token.expires_at is not None

    async def test_refresh_wraps_exchange_failure_as_refresh_failure(
        self,
    ) -> None:
        from synthorg.integrations.errors import TokenRefreshFailedError

        flow = AuthorizationCodeFlow()
        resp = _mock_token_response({})  # no access_token

        client_mock = AsyncMock()
        client_mock.post.return_value = resp

        async def _enter(self: Any) -> AsyncMock:
            return client_mock

        async def _exit(self: Any, *_: Any) -> None:
            return None

        with patch(
            "synthorg.integrations.oauth.flows.authorization_code.httpx.AsyncClient"
        ) as client_cls:
            client_cls.return_value.__aenter__ = _enter
            client_cls.return_value.__aexit__ = _exit
            with pytest.raises(TokenRefreshFailedError):
                await flow.refresh_token(
                    token_url="https://example.com/token",
                    client_id="cid",
                    client_secret="csec",
                    refresh_token="rtk",
                )


@pytest.mark.integration
class TestCallbackHandler:
    async def test_callback_persists_tokens_via_catalog(self) -> None:
        now = datetime.now(UTC)
        state = OAuthState(
            state_token=NotBlankStr("state-1"),
            connection_name=NotBlankStr("conn-1"),
            pkce_verifier=NotBlankStr("verifier"),
            scopes_requested="read",
            redirect_uri="https://app.example.com/cb",
            created_at=now,
            expires_at=now + timedelta(hours=1),
        )
        state_repo = MagicMock()
        state_repo.get = AsyncMock(return_value=state)
        state_repo.delete = AsyncMock()

        stored_tokens: dict[str, str] = {}

        async def _store(
            name: str,
            *,
            access_token: str,
            refresh_token: str | None = None,
        ) -> None:
            stored_tokens["access"] = access_token
            if refresh_token:
                stored_tokens["refresh"] = refresh_token

        catalog = MagicMock()
        catalog.get_or_raise = AsyncMock(
            return_value=Connection(
                name=NotBlankStr("conn-1"),
                connection_type=ConnectionType.OAUTH_APP,
                auth_method=AuthMethod.OAUTH2,
            ),
        )
        catalog.get_credentials = AsyncMock(
            return_value={
                "token_url": "https://example.com/token",
                "client_id": "cid",
                "client_secret": "csec",
            },
        )
        catalog.store_oauth_tokens = AsyncMock(side_effect=_store)
        catalog.update = AsyncMock()

        fake_flow = MagicMock()
        fake_flow.exchange_code = AsyncMock(
            return_value=MagicMock(
                access_token="new-access",
                refresh_token="new-refresh",
                expires_at=now + timedelta(seconds=3600),
            ),
        )

        result = await handle_oauth_callback(
            state_param="state-1",
            code="auth-code",
            state_repo=state_repo,
            catalog=catalog,
            flow=fake_flow,
        )
        assert result == "conn-1"
        assert stored_tokens == {"access": "new-access", "refresh": "new-refresh"}
        catalog.store_oauth_tokens.assert_awaited_once()
        catalog.update.assert_awaited()

    async def test_callback_rejects_expired_state(self) -> None:
        past = datetime.now(UTC) - timedelta(hours=2)
        state = OAuthState(
            state_token=NotBlankStr("state-expired"),
            connection_name=NotBlankStr("conn-1"),
            created_at=past - timedelta(hours=1),
            expires_at=past,
        )
        state_repo = MagicMock()
        state_repo.get = AsyncMock(return_value=state)
        state_repo.delete = AsyncMock()
        catalog = MagicMock()
        with pytest.raises(InvalidStateError):
            await handle_oauth_callback(
                state_param="state-expired",
                code="auth-code",
                state_repo=state_repo,
                catalog=catalog,
            )

    async def test_callback_rejects_missing_credentials(self) -> None:
        now = datetime.now(UTC)
        state = OAuthState(
            state_token=NotBlankStr("state-missing"),
            connection_name=NotBlankStr("conn-1"),
            pkce_verifier=NotBlankStr("verifier"),
            expires_at=now + timedelta(hours=1),
        )
        state_repo = MagicMock()
        state_repo.get = AsyncMock(return_value=state)
        state_repo.delete = AsyncMock()
        catalog = MagicMock()
        catalog.get_or_raise = AsyncMock(
            return_value=Connection(
                name=NotBlankStr("conn-1"),
                connection_type=ConnectionType.OAUTH_APP,
                auth_method=AuthMethod.OAUTH2,
            ),
        )
        catalog.get_credentials = AsyncMock(return_value={})
        with pytest.raises(TokenExchangeFailedError):
            await handle_oauth_callback(
                state_param="state-missing",
                code="auth-code",
                state_repo=state_repo,
                catalog=catalog,
            )


@pytest.mark.integration
class TestClientCredentialsFlow:
    async def test_exchange_returns_raw_access_token(self) -> None:
        flow = ClientCredentialsFlow()
        resp = _mock_token_response(
            {
                "access_token": "m2m-token",
                "token_type": "Bearer",
                "expires_in": 600,
                "scope": "read write",
            }
        )
        client_mock = AsyncMock()
        client_mock.post.return_value = resp

        async def _enter(self: Any) -> AsyncMock:
            return client_mock

        async def _exit(self: Any, *_: Any) -> None:
            return None

        with patch(
            "synthorg.integrations.oauth.flows.client_credentials.httpx.AsyncClient"
        ) as client_cls:
            client_cls.return_value.__aenter__ = _enter
            client_cls.return_value.__aexit__ = _exit
            token = await flow.exchange(
                token_url="https://example.com/token",
                client_id="cid",
                client_secret="csec",
                scopes=("read", "write"),
            )
        assert token.access_token == "m2m-token"
        assert token.refresh_token is None
        assert token.scope_granted == "read write"


@pytest.mark.integration
class TestDeviceFlow:
    async def test_device_flow_polling_grants_token(self) -> None:
        flow = DeviceFlow()

        start_resp = _mock_token_response(
            {
                "device_code": "dev-code",
                "user_code": "USR-123",
                "verification_uri": "https://example.com/activate",
                "interval": 1,
                "expires_in": 600,
            }
        )
        pending_resp = _mock_token_response({"error": "authorization_pending"})
        granted_resp = _mock_token_response(
            {
                "access_token": "dev-token",
                "refresh_token": "dev-refresh",
                "token_type": "Bearer",
                "expires_in": 1800,
            }
        )
        client_mock = AsyncMock()
        client_mock.post.side_effect = [
            start_resp,
            pending_resp,
            granted_resp,
        ]

        async def _enter(self: Any) -> AsyncMock:
            return client_mock

        async def _exit(self: Any, *_: Any) -> None:
            return None

        with (
            patch(
                "synthorg.integrations.oauth.flows.device_flow.httpx.AsyncClient"
            ) as client_cls,
            patch(
                "synthorg.integrations.oauth.flows.device_flow.asyncio.sleep",
                new=AsyncMock(),
            ),
        ):
            client_cls.return_value.__aenter__ = _enter
            client_cls.return_value.__aexit__ = _exit

            result = await flow.request_device_code(
                device_authorization_url="https://example.com/device",
                client_id="cid",
                scopes=("read",),
            )
            assert result.user_code == "USR-123"

            token = await flow.poll_for_token(
                token_url="https://example.com/token",
                client_id="cid",
                device_code=result.device_code,
                interval=1,
                max_wait_seconds=60,
            )
        assert token.access_token == "dev-token"
        assert token.refresh_token == "dev-refresh"
