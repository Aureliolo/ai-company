"""OAuth 2.1 client credentials flow (machine-to-machine)."""

import json
from datetime import UTC, datetime, timedelta

import httpx

from synthorg.integrations.connections.models import OAuthToken
from synthorg.integrations.errors import TokenExchangeFailedError
from synthorg.observability import get_logger
from synthorg.observability.events.integrations import (
    OAUTH_TOKEN_EXCHANGE_FAILED,
    OAUTH_TOKEN_EXCHANGED,
)

logger = get_logger(__name__)


class ClientCredentialsFlow:
    """OAuth 2.1 client credentials flow for M2M auth.

    No user interaction required.  The client authenticates
    directly with its own credentials.
    """

    @property
    def grant_type(self) -> str:
        """OAuth grant type identifier."""
        return "client_credentials"

    @property
    def supports_refresh(self) -> bool:
        """Whether this flow produces refresh tokens."""
        return False

    async def exchange(
        self,
        *,
        token_url: str,
        client_id: str,
        client_secret: str,
        scopes: tuple[str, ...] = (),
    ) -> OAuthToken:
        """Exchange client credentials for an access token.

        Args:
            token_url: Token endpoint URL.
            client_id: OAuth client ID.
            client_secret: OAuth client secret.
            scopes: Requested scopes.

        Returns:
            The granted ``OAuthToken`` (no refresh token).

        Raises:
            TokenExchangeFailedError: If the exchange fails.
        """
        payload: dict[str, str] = {
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
        }
        if scopes:
            payload["scope"] = " ".join(scopes)

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
            msg = f"Client credentials exchange failed: {exc}"
            raise TokenExchangeFailedError(msg) from exc

        if not isinstance(data, dict):
            logger.warning(
                OAUTH_TOKEN_EXCHANGE_FAILED,
                error="token response is not a JSON object",
                response_type=type(data).__name__,
            )
            msg = (
                "Client credentials response is not a JSON object: "
                f"{type(data).__name__}"
            )
            raise TokenExchangeFailedError(msg)
        access_token_raw = data.get("access_token")
        if not isinstance(access_token_raw, str) or not access_token_raw:
            logger.warning(
                OAUTH_TOKEN_EXCHANGE_FAILED,
                error="missing or invalid access_token",
            )
            msg = "No valid access_token in client credentials response"
            raise TokenExchangeFailedError(msg)
        access_token = access_token_raw

        expires_in = data.get("expires_in")
        expires_at = None
        if isinstance(expires_in, int) and expires_in > 0:
            expires_at = datetime.now(UTC) + timedelta(seconds=expires_in)

        logger.info(OAUTH_TOKEN_EXCHANGED, grant_type="client_credentials")
        return OAuthToken(
            access_token=access_token,
            token_type=str(data.get("token_type", "Bearer")),
            expires_at=expires_at,
            scope_granted=str(data.get("scope", "")),
        )
