"""OAuth callback handler.

Provides the ``handle_oauth_callback`` function used by the
OAuth API controller to process authorization code callbacks.
"""

from synthorg.integrations.connections.catalog import ConnectionCatalog  # noqa: TC001
from synthorg.integrations.errors import (
    InvalidStateError,
    TokenExchangeFailedError,
)
from synthorg.integrations.oauth.flows.authorization_code import (
    AuthorizationCodeFlow,
)
from synthorg.observability import get_logger
from synthorg.observability.events.integrations import (
    OAUTH_CALLBACK_RECEIVED,
    OAUTH_FLOW_COMPLETED,
    OAUTH_FLOW_FAILED,
    OAUTH_STATE_INVALID,
)
from synthorg.persistence.repositories_integrations import (
    OAuthStateRepository,  # noqa: TC001
)

logger = get_logger(__name__)


async def handle_oauth_callback(
    *,
    state_param: str,
    code: str,
    state_repo: OAuthStateRepository,
    catalog: ConnectionCatalog,
    flow: AuthorizationCodeFlow | None = None,
) -> str:
    """Process an OAuth authorization code callback.

    Validates the state token, exchanges the code for tokens,
    and updates the connection in the catalog.

    Args:
        state_param: The state parameter from the callback URL.
        code: The authorization code.
        state_repo: Repository for looking up OAuth states.
        catalog: Connection catalog for credential storage.
        flow: Authorization code flow instance (default: new).

    Returns:
        The connection name that was updated.

    Raises:
        InvalidStateError: If the state token is invalid or expired.
        TokenExchangeFailedError: If the code exchange fails.
    """
    logger.info(OAUTH_CALLBACK_RECEIVED, state=state_param[:8] + "...")

    oauth_state = await state_repo.get(state_param)
    if oauth_state is None:
        logger.warning(OAUTH_STATE_INVALID, state=state_param[:8] + "...")
        msg = "Invalid or expired OAuth state token"
        raise InvalidStateError(msg)

    await state_repo.delete(state_param)

    conn = await catalog.get_or_raise(oauth_state.connection_name)
    credentials = await catalog.get_credentials(conn.name)

    auth_flow = flow or AuthorizationCodeFlow()
    try:
        token = await auth_flow.exchange_code(
            token_url=credentials.get("token_url", ""),
            client_id=credentials.get("client_id", ""),
            client_secret=credentials.get("client_secret", ""),
            state=oauth_state,
            code=code,
            redirect_uri=oauth_state.redirect_uri,
        )
    except TokenExchangeFailedError:
        logger.warning(
            OAUTH_FLOW_FAILED,
            connection_name=conn.name,
        )
        raise

    # Update connection metadata with token expiry
    meta_updates = dict(conn.metadata)
    if token.expires_at:
        meta_updates["token_expires_at"] = token.expires_at.isoformat()
    await catalog.update(conn.name, metadata=meta_updates)

    logger.info(
        OAUTH_FLOW_COMPLETED,
        connection_name=conn.name,
    )
    return conn.name
