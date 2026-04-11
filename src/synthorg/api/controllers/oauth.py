"""OAuth API controller.

Endpoints for initiating OAuth flows, handling callbacks,
and checking token status.
"""

from typing import Any

from litestar import Controller, get, post
from litestar.datastructures import State  # noqa: TC002
from litestar.params import Parameter

from synthorg.api.dto import ApiResponse
from synthorg.api.errors import NotFoundError
from synthorg.api.guards import require_read_access, require_write_access
from synthorg.integrations.errors import (
    ConnectionNotFoundError,
)
from synthorg.integrations.oauth.flows.authorization_code import (
    AuthorizationCodeFlow,
)
from synthorg.observability import get_logger

logger = get_logger(__name__)


class OAuthController(Controller):
    """OAuth flow management endpoints."""

    path = "/api/v1/oauth"
    tags = ["Integrations"]  # noqa: RUF012

    @post(
        "/initiate",
        guards=[require_write_access],
        summary="Start an OAuth flow",
    )
    async def initiate_flow(
        self,
        state: State,
        data: dict[str, Any],
    ) -> ApiResponse[dict[str, str]]:
        """Initiate an OAuth authorization code flow.

        Returns the authorization URL for the user to visit.
        """
        catalog = state["app_state"].connection_catalog
        connection_name = data.get("connection_name", "")

        try:
            conn = await catalog.get_or_raise(connection_name)
        except ConnectionNotFoundError as exc:
            raise NotFoundError(str(exc)) from exc

        credentials = await catalog.get_credentials(connection_name)

        flow = AuthorizationCodeFlow()
        config = state["app_state"].config.integrations.oauth

        auth_url, oauth_state = await flow.start_flow(
            auth_url=credentials.get("auth_url", ""),
            token_url=credentials.get("token_url", ""),
            client_id=credentials.get("client_id", ""),
            client_secret=credentials.get("client_secret", ""),
            scopes=tuple(data.get("scopes", [])),
            redirect_uri=(
                config.redirect_uri_base + "/api/v1/oauth/callback"
                if config.redirect_uri_base
                else data.get("redirect_uri", "")
            ),
        )

        # Persist the OAuth state
        updated_state = oauth_state.model_copy(
            update={"connection_name": conn.name},
        )
        persistence = state["app_state"].persistence
        await persistence.oauth_states.save(updated_state)

        return ApiResponse(
            data={
                "authorization_url": auth_url,
                "state_token": updated_state.state_token,
            },
        )

    @get(
        "/callback",
        summary="OAuth callback",
    )
    async def callback(
        self,
        state: State,
        code: str = Parameter(description="Authorization code"),
        state_param: str = Parameter(
            query="state",
            description="OAuth state token",
        ),
    ) -> ApiResponse[dict[str, Any]]:
        """Handle OAuth provider callback."""
        from synthorg.integrations.oauth.callback_handler import (  # noqa: PLC0415
            handle_oauth_callback,
        )

        persistence = state["app_state"].persistence
        catalog = state["app_state"].connection_catalog

        connection_name = await handle_oauth_callback(
            state_param=state_param,
            code=code,
            state_repo=persistence.oauth_states,
            catalog=catalog,
        )
        return ApiResponse(
            data={
                "status": "connected",
                "connection_name": connection_name,
            },
        )

    @get(
        "/status/{connection_name:str}",
        guards=[require_read_access],
        summary="Check OAuth token status",
    )
    async def token_status(
        self,
        state: State,
        connection_name: str,
    ) -> ApiResponse[dict[str, Any]]:
        """Check the OAuth token status for a connection."""
        catalog = state["app_state"].connection_catalog
        try:
            conn = await catalog.get_or_raise(connection_name)
        except ConnectionNotFoundError as exc:
            raise NotFoundError(str(exc)) from exc

        expires_at = conn.metadata.get("token_expires_at")
        return ApiResponse(
            data={
                "connection_name": connection_name,
                "has_token": bool(conn.secret_refs),
                "token_expires_at": expires_at,
            },
        )
