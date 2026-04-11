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
    Connection,
    ConnectionStatus,
)
from synthorg.integrations.errors import TokenRefreshFailedError
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
        self._lifecycle_lock = asyncio.Lock()

    async def start(self) -> None:
        """Start the background refresh loop."""
        async with self._lifecycle_lock:
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
        async with self._lifecycle_lock:
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
            # Token expiry is tracked via connection metadata, which
            # is externally editable. Guard everything that could
            # escape as a ``TypeError`` (non-string value) or
            # comparison failure (naive datetime) so a single bad
            # connection does not abort the sweep and skip every
            # later OAuth connection.
            expiry_raw = conn.metadata.get("token_expires_at")
            if not isinstance(expiry_raw, str) or not expiry_raw.strip():
                continue
            try:
                expiry = datetime.fromisoformat(expiry_raw.strip())
            except TypeError, ValueError:
                logger.warning(
                    OAUTH_TOKEN_REFRESH_FAILED,
                    connection_name=conn.name,
                    error="malformed token_expires_at metadata",
                    value=expiry_raw,
                )
                continue
            # Coerce naive datetimes to UTC so the comparison below
            # cannot raise with a mixed tz/non-tz operands.
            if expiry.tzinfo is None:
                expiry = expiry.replace(tzinfo=UTC)

            try:
                is_expired = expiry <= now
                is_in_window = expiry <= threshold
            except TypeError:
                logger.warning(
                    OAUTH_TOKEN_REFRESH_FAILED,
                    connection_name=conn.name,
                    error="token_expires_at comparison failed",
                )
                continue

            if is_expired:
                logger.warning(
                    OAUTH_TOKEN_EXPIRED,
                    connection_name=conn.name,
                )
                await self._catalog.update_health(
                    conn.name,
                    status=ConnectionStatus.DEGRADED,
                    checked_at=now,
                )
            elif is_in_window:
                await self._refresh_one(conn, now)

    async def _refresh_one(self, conn: Connection, now: datetime) -> None:
        """Refresh tokens for one connection and persist them.

        Any failure is logged and the connection is flipped to
        ``DEGRADED``; exceptions are swallowed here so one failing
        connection never crashes the refresh loop.
        """
        try:
            credentials = await self._catalog.get_credentials(conn.name)
        except Exception:
            logger.exception(
                OAUTH_TOKEN_REFRESH_FAILED,
                connection_name=conn.name,
                error="credential load failed",
            )
            await self._catalog.update_health(
                conn.name,
                status=ConnectionStatus.DEGRADED,
                checked_at=now,
            )
            return

        token_url = credentials.get("token_url", "")
        client_id = credentials.get("client_id", "")
        client_secret = credentials.get("client_secret", "")
        refresh_token = credentials.get("refresh_token", "")
        if not (token_url and client_id and client_secret and refresh_token):
            logger.warning(
                OAUTH_TOKEN_REFRESH_FAILED,
                connection_name=conn.name,
                reason="missing refresh credentials",
            )
            await self._catalog.update_health(
                conn.name,
                status=ConnectionStatus.DEGRADED,
                checked_at=now,
            )
            return

        try:
            refreshed = await self._flow.refresh_token(
                token_url=token_url,
                client_id=client_id,
                client_secret=client_secret,
                refresh_token=refresh_token,
            )
        except TokenRefreshFailedError:
            logger.warning(
                OAUTH_TOKEN_REFRESH_FAILED,
                connection_name=conn.name,
            )
            await self._catalog.update_health(
                conn.name,
                status=ConnectionStatus.DEGRADED,
                checked_at=now,
            )
            return

        if not refreshed.access_token:
            logger.warning(
                OAUTH_TOKEN_REFRESH_FAILED,
                connection_name=conn.name,
                reason="refresh returned no access_token",
            )
            # Treat an empty refresh result as a failure path so
            # the connection's health flips to ``DEGRADED`` and an
            # operator notices it, instead of silently returning
            # and leaving the old expired token in place.
            await self._catalog.update_health(
                conn.name,
                status=ConnectionStatus.DEGRADED,
                checked_at=now,
            )
            return

        try:
            await self._catalog.store_oauth_tokens(
                conn.name,
                access_token=refreshed.access_token,
                refresh_token=refreshed.refresh_token,
            )
            if refreshed.expires_at is not None:
                meta_updates = dict(conn.metadata)
                meta_updates["token_expires_at"] = refreshed.expires_at.isoformat()
                await self._catalog.update(conn.name, metadata=meta_updates)
        except Exception:
            # A write failure after a successful refresh leaves the
            # connection state inconsistent. Swallow the exception
            # so the sweep continues with the next connection, but
            # flip health to ``DEGRADED`` and log the failure with
            # the exception chain.
            logger.exception(
                OAUTH_TOKEN_REFRESH_FAILED,
                connection_name=conn.name,
                error="failed to persist refreshed tokens",
            )
            try:
                await self._catalog.update_health(
                    conn.name,
                    status=ConnectionStatus.DEGRADED,
                    checked_at=now,
                )
            except Exception:
                logger.exception(
                    OAUTH_TOKEN_REFRESH_FAILED,
                    connection_name=conn.name,
                    error="update_health failed after persistence failure",
                )
            return

        logger.info(
            OAUTH_TOKEN_REFRESHED,
            connection_name=conn.name,
            has_refresh=refreshed.refresh_token is not None,
            note="proactive refresh completed",
        )
