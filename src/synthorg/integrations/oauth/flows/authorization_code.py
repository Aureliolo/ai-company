"""OAuth 2.1 authorization code flow with PKCE."""

import json
import secrets as stdlib_secrets
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

import httpx

from synthorg.core.types import NotBlankStr
from synthorg.integrations.connections.models import (
    OAuthState,
    OAuthToken,
)
from synthorg.integrations.errors import (
    TokenExchangeFailedError,
    TokenRefreshFailedError,
)
from synthorg.integrations.oauth.pkce import (
    generate_code_challenge,
    generate_code_verifier,
)
from synthorg.observability import get_logger
from synthorg.observability.events.integrations import (
    OAUTH_FLOW_STARTED,
    OAUTH_TOKEN_EXCHANGE_FAILED,
    OAUTH_TOKEN_EXCHANGED,
    OAUTH_TOKEN_REFRESH_FAILED,
    OAUTH_TOKEN_REFRESHED,
)

logger = get_logger(__name__)


class AuthorizationCodeFlow:
    """OAuth 2.1 authorization code flow with PKCE.

    Implements the three-step flow: start (build auth URL),
    exchange (code for tokens), and refresh.
    """

    @property
    def grant_type(self) -> str:
        """OAuth grant type identifier."""
        return "authorization_code"

    @property
    def supports_refresh(self) -> bool:
        """Whether this flow produces refresh tokens."""
        return True

    async def start_flow(  # noqa: PLR0913
        self,
        *,
        auth_url: str,
        token_url: str,  # noqa: ARG002
        client_id: str,
        client_secret: str,  # noqa: ARG002
        scopes: tuple[str, ...],
        redirect_uri: str,
    ) -> tuple[str, OAuthState]:
        """Build the authorization URL and create state.

        Returns:
            (authorization_url, OAuthState) tuple.
        """
        state_token = stdlib_secrets.token_urlsafe(32)
        verifier = generate_code_verifier()
        challenge = generate_code_challenge(verifier)

        params = {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": " ".join(scopes),
            "state": state_token,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
        authorization_url = f"{auth_url}?{urlencode(params)}"

        now = datetime.now(UTC)
        oauth_state = OAuthState(
            state_token=NotBlankStr(state_token),
            connection_name=NotBlankStr("pending"),
            pkce_verifier=NotBlankStr(verifier),
            scopes_requested=" ".join(scopes),
            redirect_uri=redirect_uri,
            created_at=now,
            expires_at=now + timedelta(hours=1),
        )
        logger.info(OAUTH_FLOW_STARTED, grant_type="authorization_code")
        return authorization_url, oauth_state

    async def exchange_code(  # noqa: PLR0913
        self,
        *,
        token_url: str,
        client_id: str,
        client_secret: str,
        state: OAuthState,
        code: str,
        redirect_uri: str,
    ) -> OAuthToken:
        """Exchange authorization code for tokens.

        Raises:
            TokenExchangeFailedError: If the exchange fails.
        """
        if state.pkce_verifier is None:
            msg = "PKCE verifier missing from OAuth state"
            raise TokenExchangeFailedError(msg)

        payload = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": client_id,
            "client_secret": client_secret,
            "code_verifier": state.pkce_verifier,
        }
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(token_url, data=payload)
                resp.raise_for_status()
                data = resp.json()
        except (httpx.HTTPError, json.JSONDecodeError) as exc:
            logger.exception(
                OAUTH_TOKEN_EXCHANGE_FAILED,
                error=str(exc),
            )
            msg = f"Token exchange failed: {exc}"
            raise TokenExchangeFailedError(msg) from exc

        return self._parse_token_response(data, "exchange")

    async def refresh_token(
        self,
        *,
        token_url: str,
        client_id: str,
        client_secret: str,
        refresh_token: str,
    ) -> OAuthToken:
        """Refresh an access token.

        Raises:
            TokenRefreshFailedError: If the refresh fails or the
                response cannot be parsed.
        """
        payload = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": client_id,
            "client_secret": client_secret,
        }
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(token_url, data=payload)
                resp.raise_for_status()
                data = resp.json()
        except (httpx.HTTPError, json.JSONDecodeError) as exc:
            logger.exception(
                OAUTH_TOKEN_REFRESH_FAILED,
                error=str(exc),
            )
            msg = f"Token refresh failed: {exc}"
            raise TokenRefreshFailedError(msg) from exc

        try:
            return self._parse_token_response(data, "refresh")
        except TokenExchangeFailedError as exc:
            # Normalize refresh failures to the refresh error domain.
            logger.exception(
                OAUTH_TOKEN_REFRESH_FAILED,
                error=str(exc),
            )
            raise TokenRefreshFailedError(str(exc)) from exc

    @staticmethod
    def _parse_token_response(
        data: dict[str, object],
        operation: str,
    ) -> OAuthToken:
        """Parse a token endpoint response into an OAuthToken.

        Returns an ``OAuthToken`` with raw ``access_token`` /
        ``refresh_token`` populated. The caller is responsible
        for persisting them via
        ``ConnectionCatalog.store_oauth_tokens``.
        """
        access_token = str(data.get("access_token", ""))
        if not access_token:
            msg = f"No access_token in {operation} response"
            raise TokenExchangeFailedError(msg)

        expires_in = data.get("expires_in")
        expires_at = None
        if isinstance(expires_in, int) and expires_in > 0:
            expires_at = datetime.now(UTC) + timedelta(seconds=expires_in)

        refresh = data.get("refresh_token")
        refresh_raw: str | None = None
        if refresh and isinstance(refresh, str):
            refresh_raw = refresh

        event = (
            OAUTH_TOKEN_EXCHANGED if operation == "exchange" else OAUTH_TOKEN_REFRESHED
        )
        logger.info(event, has_refresh=refresh_raw is not None)

        return OAuthToken(
            access_token=access_token,
            refresh_token=refresh_raw,
            token_type=str(data.get("token_type", "Bearer")),
            expires_at=expires_at,
            scope_granted=str(data.get("scope", "")),
        )
