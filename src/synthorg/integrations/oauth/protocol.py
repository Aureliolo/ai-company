"""OAuth flow strategy protocol."""

from typing import Protocol, runtime_checkable

from synthorg.integrations.connections.models import (  # noqa: TC001
    OAuthState,
    OAuthToken,
)


@runtime_checkable
class OAuthFlowStrategy(Protocol):
    """Pluggable OAuth 2.1 flow implementation.

    Each concrete strategy handles one grant type (authorization
    code + PKCE, device flow, client credentials).
    """

    @property
    def grant_type(self) -> str:
        """OAuth grant type identifier."""
        ...

    @property
    def supports_refresh(self) -> bool:
        """Whether this flow produces refresh tokens."""
        ...

    async def start_flow(  # noqa: PLR0913
        self,
        *,
        auth_url: str,
        token_url: str,
        client_id: str,
        client_secret: str,
        scopes: tuple[str, ...],
        redirect_uri: str,
    ) -> tuple[str, OAuthState]:
        """Initiate the flow.

        Returns:
            A tuple of (authorization_url_or_user_code, OAuthState).

        Raises:
            OAuthFlowError: If the flow cannot be started.
        """
        ...

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
        """Exchange an authorization code for tokens.

        Raises:
            TokenExchangeFailedError: If the exchange fails.
        """
        ...

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
            TokenRefreshFailedError: If the refresh fails.
        """
        ...
