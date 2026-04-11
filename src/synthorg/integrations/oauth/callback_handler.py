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
    persists the raw access/refresh tokens via the connection
    catalog (which writes them through the configured secret
    backend), and updates the connection's token expiry metadata.

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
        TokenExchangeFailedError: If the code exchange fails or the
            exchange credentials (token_url / client_id /
            client_secret) are missing from the connection.
    """
    logger.info(OAUTH_CALLBACK_RECEIVED, state=state_param[:8] + "...")

    oauth_state = await state_repo.get(state_param)
    if oauth_state is None:
        logger.warning(OAUTH_STATE_INVALID, state=state_param[:8] + "...")
        msg = "Invalid or expired OAuth state token"
        raise InvalidStateError(msg)

    from datetime import UTC, datetime  # noqa: PLC0415

    if oauth_state.expires_at < datetime.now(UTC):
        await state_repo.delete(state_param)
        logger.warning(
            OAUTH_STATE_INVALID,
            state=state_param[:8] + "...",
            reason="expired",
        )
        msg = "OAuth state token expired"
        raise InvalidStateError(msg)

    await state_repo.delete(state_param)

    conn = await catalog.get_or_raise(oauth_state.connection_name)
    credentials = await catalog.get_credentials(conn.name)

    token_url = credentials.get("token_url", "")
    client_id = credentials.get("client_id", "")
    client_secret = credentials.get("client_secret", "")
    missing = [
        label
        for label, value in (
            ("token_url", token_url),
            ("client_id", client_id),
            ("client_secret", client_secret),
        )
        if not value
    ]
    if missing:
        logger.warning(
            OAUTH_FLOW_FAILED,
            connection_name=conn.name,
            missing=",".join(missing),
        )
        msg = (
            "Cannot exchange OAuth code: connection is missing "
            f"credentials: {', '.join(missing)}"
        )
        raise TokenExchangeFailedError(msg)

    auth_flow = flow or AuthorizationCodeFlow()
    try:
        token = await auth_flow.exchange_code(
            token_url=token_url,
            client_id=client_id,
            client_secret=client_secret,
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

    if not token.access_token:
        logger.warning(
            OAUTH_FLOW_FAILED,
            connection_name=conn.name,
            reason="flow returned no access_token",
        )
        msg = "OAuth flow returned no access_token"
        raise TokenExchangeFailedError(msg)

    # Persist access/refresh tokens via the secret backend.
    await catalog.store_oauth_tokens(
        conn.name,
        access_token=token.access_token,
        refresh_token=token.refresh_token,
    )

    # Update connection metadata with token expiry.
    meta_updates = dict(conn.metadata)
    if token.expires_at:
        meta_updates["token_expires_at"] = token.expires_at.isoformat()
    else:
        # New token has no expiry (non-expiring grant). Drop any
        # stale ``token_expires_at`` carried over from a prior flow
        # so we do not incorrectly mark the token as expired later.
        meta_updates.pop("token_expires_at", None)
    await catalog.update(conn.name, metadata=meta_updates)

    logger.info(
        OAUTH_FLOW_COMPLETED,
        connection_name=conn.name,
    )
    return conn.name
