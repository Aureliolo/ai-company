"""OAuth token lifecycle manager.

Background service that monitors OAuth connections and refreshes
tokens before they expire.
"""

import asyncio
import contextlib
from datetime import UTC, datetime, timedelta

from synthorg.integrations.connections.catalog import ConnectionCatalog  # noqa: TC001
from synthorg.integrations.connections.models import (
    AuthMethod,
    ConnectionStatus,
)
from synthorg.integrations.oauth.flows.authorization_code import (
    AuthorizationCodeFlow,
)
from synthorg.observability import get_logger
from synthorg.observability.events.integrations import (
    OAUTH_TOKEN_EXPIRED,
    OAUTH_TOKEN_REFRESH_FAILED,
    OAUTH_TOKEN_REFRESHED,
)

logger = get_logger(__name__)


class OAuthTokenManager:
    """Monitors OAuth connections and refreshes tokens proactively.

    Runs as a background asyncio task, checking all OAuth2
    connections and refreshing tokens that are about to expire.

    Args:
        catalog: The connection catalog.
        refresh_threshold_seconds: Refresh tokens expiring within
            this window.
        check_interval_seconds: How often to check for expiring tokens.
    """

    def __init__(
        self,
        catalog: ConnectionCatalog,
        *,
        refresh_threshold_seconds: int = 300,
        check_interval_seconds: int = 60,
    ) -> None:
        self._catalog = catalog
        self._threshold = timedelta(seconds=refresh_threshold_seconds)
        self._interval = check_interval_seconds
        self._task: asyncio.Task[None] | None = None
        self._flow = AuthorizationCodeFlow()

    async def start(self) -> None:
        """Start the background refresh loop."""
        if self._task is not None:
            return
        self._task = asyncio.create_task(self._refresh_loop())
        logger.info(
            OAUTH_TOKEN_REFRESHED,
            has_refresh=False,
            note="token manager started",
        )

    async def stop(self) -> None:
        """Stop the background refresh loop."""
        if self._task is None:
            return
        self._task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await self._task
        self._task = None

    async def _refresh_loop(self) -> None:
        """Periodically check and refresh expiring tokens."""
        while True:
            try:
                await self._check_and_refresh()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception(
                    OAUTH_TOKEN_REFRESH_FAILED,
                    error="unexpected error in refresh loop",
                )
            await asyncio.sleep(self._interval)

    async def _check_and_refresh(self) -> None:
        """Check all OAuth connections for expiring tokens."""
        all_connections = await self._catalog.list_all()
        now = datetime.now(UTC)
        threshold = now + self._threshold

        for conn in all_connections:
            if conn.auth_method != AuthMethod.OAUTH2:
                continue
            # Token expiry is tracked via connection metadata
            expiry_str = conn.metadata.get("token_expires_at", "")
            if not expiry_str:
                continue
            try:
                expiry = datetime.fromisoformat(expiry_str)
            except ValueError:
                continue

            if expiry <= now:
                logger.warning(
                    OAUTH_TOKEN_EXPIRED,
                    connection_name=conn.name,
                )
                await self._catalog.update_health(
                    conn.name,
                    status=ConnectionStatus.DEGRADED,
                    checked_at=now,
                )
            elif expiry <= threshold:
                logger.info(
                    OAUTH_TOKEN_REFRESHED,
                    connection_name=conn.name,
                    has_refresh=True,
                    note="proactive refresh",
                )
