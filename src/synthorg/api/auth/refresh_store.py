"""Refresh token storage with one-time rotation support.

Refresh tokens are opaque strings stored as HMAC-SHA256 hashes
(same key as API keys).  Each token is single-use: consuming
it atomically marks it as used and returns the associated
session/user info for re-issuance.

The public surface is the :class:`RefreshStore` protocol; two
concrete implementations back it:

* :class:`SqliteRefreshStore` -- wraps an ``aiosqlite.Connection``.
* :class:`PostgresRefreshStore` -- wraps a
  ``psycopg_pool.AsyncConnectionPool``.

Lifecycle code picks the concrete class that matches the active
persistence backend (see ``synthorg.api.lifecycle``).
"""

from collections.abc import Callable  # noqa: TC003
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Protocol, Self, runtime_checkable

import aiosqlite  # noqa: TC002
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from synthorg.core.types import NotBlankStr  # noqa: TC001
from synthorg.observability import get_logger
from synthorg.observability.events.api import (
    API_AUTH_REFRESH_CLEANUP,
    API_AUTH_REFRESH_CONSUMED,
    API_AUTH_REFRESH_CREATED,
    API_AUTH_REFRESH_REJECTED,
    API_AUTH_REFRESH_REVOKED,
)

if TYPE_CHECKING:
    from psycopg_pool import AsyncConnectionPool


def _import_dict_row() -> Any:
    """Lazily resolve ``psycopg.rows.dict_row``.

    Kept out of the module-level import block so Sqlite-only deployments
    never need the optional ``psycopg`` dependency at import time.
    ``AsyncConnectionPool`` is similarly deferred via ``TYPE_CHECKING``.
    """
    from psycopg.rows import dict_row  # noqa: PLC0415

    return dict_row


logger = get_logger(__name__)


@runtime_checkable
class RefreshStore(Protocol):
    """Refresh token store contract implemented by SQLite and Postgres backends.

    All methods are async. Method docstrings on this protocol describe the
    contract; concrete implementations reuse the same semantics.
    """

    async def create(
        self,
        token_hash: str,
        session_id: str,
        user_id: str,
        expires_at: datetime,
    ) -> None:
        """Store a new refresh token."""
        ...

    async def consume(
        self,
        token_hash: str,
        *,
        is_session_revoked: Callable[[str], bool] | None = None,
    ) -> RefreshRecord | None:
        """Atomically consume a refresh token."""
        ...

    async def revoke_by_session(self, session_id: str) -> int:
        """Mark all refresh tokens for a session as used."""
        ...

    async def revoke_by_user(self, user_id: str) -> int:
        """Mark all refresh tokens for a user as used."""
        ...

    async def cleanup_expired(self) -> int:
        """Remove expired tokens."""
        ...


class RefreshRecord(BaseModel):
    """A stored refresh token record.

    Attributes:
        token_hash: HMAC-SHA256 hash of the opaque token.
        session_id: Associated JWT session (``jti``).
        user_id: Token owner's user ID.
        expires_at: Expiry timestamp.
        used: Whether the token has been consumed.
        created_at: Creation timestamp.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    token_hash: NotBlankStr
    session_id: NotBlankStr
    user_id: NotBlankStr
    expires_at: AwareDatetime
    used: bool = False
    created_at: AwareDatetime = Field(
        default_factory=lambda: datetime.now(UTC),
    )

    @model_validator(mode="after")
    def _validate_temporal_order(self) -> Self:
        """Ensure created_at does not exceed expires_at."""
        if self.created_at > self.expires_at:
            msg = "created_at must not be after expires_at"
            raise ValueError(msg)
        return self


class SqliteRefreshStore:
    """SQLite-backed refresh token store.

    Args:
        db: Open aiosqlite connection with ``row_factory`` set.
    """

    def __init__(self, db: aiosqlite.Connection) -> None:
        self._db = db

    async def create(
        self,
        token_hash: str,
        session_id: str,
        user_id: str,
        expires_at: datetime,
    ) -> None:
        """Store a new refresh token.

        Args:
            token_hash: HMAC-SHA256 hash of the opaque token.
            session_id: Associated JWT session ID.
            user_id: Token owner's user ID.
            expires_at: Expiry timestamp.
        """
        now = datetime.now(UTC)
        await self._db.execute(
            "INSERT INTO refresh_tokens "
            "(token_hash, session_id, user_id, expires_at, "
            "used, created_at) "
            "VALUES (?, ?, ?, ?, 0, ?)",
            (
                token_hash,
                session_id,
                user_id,
                expires_at.isoformat(),
                now.isoformat(),
            ),
        )
        await self._db.commit()
        logger.info(
            API_AUTH_REFRESH_CREATED,
            session_id=session_id,
            user_id=user_id,
        )

    async def consume(
        self,
        token_hash: str,
        *,
        is_session_revoked: Callable[[str], bool] | None = None,
    ) -> RefreshRecord | None:
        """Atomically consume a refresh token.

        Marks the token as used and returns its record.
        Returns ``None`` if the token does not exist, is
        expired, was already consumed (replay detection), or
        belongs to a revoked session.

        Args:
            token_hash: HMAC-SHA256 hash of the presented token.
            is_session_revoked: Optional sync callback (e.g.
                ``SessionStore.is_revoked``) to reject tokens
                whose session has been revoked.

        Returns:
            The token record, or ``None`` on failure.
        """
        now = datetime.now(UTC).isoformat()
        cursor = await self._db.execute(
            "UPDATE refresh_tokens SET used = 1 "
            "WHERE token_hash = ? AND used = 0 AND expires_at > ? "
            "RETURNING token_hash, session_id, user_id, "
            "expires_at, used, created_at",
            (token_hash, now),
        )
        row = await cursor.fetchone()
        await self._db.commit()

        if row is not None:
            # Reject if the associated session has been revoked.
            if is_session_revoked and is_session_revoked(
                row["session_id"],
            ):
                logger.warning(
                    API_AUTH_REFRESH_REJECTED,
                    reason="session_revoked",
                    session_id=row["session_id"][:8],
                )
                return None
            logger.info(
                API_AUTH_REFRESH_CONSUMED,
                session_id=row["session_id"],
                user_id=row["user_id"],
            )
            return RefreshRecord(
                token_hash=row["token_hash"],
                session_id=row["session_id"],
                user_id=row["user_id"],
                expires_at=datetime.fromisoformat(
                    row["expires_at"],
                ),
                used=bool(row["used"]),
                created_at=datetime.fromisoformat(
                    row["created_at"],
                ),
            )

        # Check if it was a replay (token exists but already used)
        check = await self._db.execute(
            "SELECT used FROM refresh_tokens WHERE token_hash = ?",
            (token_hash,),
        )
        replay_row = await check.fetchone()
        if replay_row is not None and replay_row["used"]:
            logger.warning(
                API_AUTH_REFRESH_REJECTED,
                reason="replay_detected",
                token_hash=token_hash[:8],
            )
        else:
            logger.warning(
                API_AUTH_REFRESH_REJECTED,
                reason="not_found_or_expired",
                token_hash=token_hash[:8],
            )
        return None

    async def revoke_by_session(self, session_id: str) -> int:
        """Mark all refresh tokens for a session as used.

        Args:
            session_id: Session ID whose tokens to revoke.

        Returns:
            Number of tokens revoked.
        """
        cursor = await self._db.execute(
            "UPDATE refresh_tokens SET used = 1 WHERE session_id = ? AND used = 0",
            (session_id,),
        )
        await self._db.commit()
        count = cursor.rowcount
        if count:
            logger.info(
                API_AUTH_REFRESH_REVOKED,
                session_id=session_id,
                revoked=count,
            )
        return count

    async def revoke_by_user(self, user_id: str) -> int:
        """Mark all refresh tokens for a user as used.

        Args:
            user_id: User ID whose tokens to revoke.

        Returns:
            Number of tokens revoked.
        """
        cursor = await self._db.execute(
            "UPDATE refresh_tokens SET used = 1 WHERE user_id = ? AND used = 0",
            (user_id,),
        )
        await self._db.commit()
        count = cursor.rowcount
        if count:
            logger.info(
                API_AUTH_REFRESH_REVOKED,
                user_id=user_id,
                revoked=count,
            )
        return count

    async def cleanup_expired(self) -> int:
        """Remove expired tokens.

        Used (consumed) tokens are retained until their expiry so
        that replay detection can still identify double-use attempts.

        Returns:
            Number of records removed.
        """
        now = datetime.now(UTC).isoformat()
        cursor = await self._db.execute(
            "DELETE FROM refresh_tokens WHERE expires_at <= ?",
            (now,),
        )
        await self._db.commit()
        count = cursor.rowcount
        if count:
            logger.info(API_AUTH_REFRESH_CLEANUP, removed=count)
        return count


class PostgresRefreshStore:
    """Postgres-backed refresh token store.

    Uses the shared ``AsyncConnectionPool`` (same one every
    Postgres repository composes against). Each operation checks
    out a connection via ``async with pool.connection() as conn``;
    the context manager auto-commits the transaction on a clean
    exit and rolls back on exception, so no explicit ``commit()``
    call is required.

    Args:
        pool: An open ``psycopg_pool.AsyncConnectionPool``.
    """

    def __init__(self, pool: AsyncConnectionPool) -> None:
        self._pool = pool
        self._dict_row = _import_dict_row()

    async def create(
        self,
        token_hash: str,
        session_id: str,
        user_id: str,
        expires_at: datetime,
    ) -> None:
        """Store a new refresh token.

        Args:
            token_hash: HMAC-SHA256 hash of the opaque token.
            session_id: Associated JWT session ID.
            user_id: Token owner's user ID.
            expires_at: Expiry timestamp.
        """
        now = datetime.now(UTC)
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                "INSERT INTO refresh_tokens "
                "(token_hash, session_id, user_id, expires_at, "
                "used, created_at) "
                "VALUES (%s, %s, %s, %s, FALSE, %s)",
                (
                    token_hash,
                    session_id,
                    user_id,
                    expires_at,
                    now,
                ),
            )
        logger.info(
            API_AUTH_REFRESH_CREATED,
            session_id=session_id,
            user_id=user_id,
        )

    async def consume(
        self,
        token_hash: str,
        *,
        is_session_revoked: Callable[[str], bool] | None = None,
    ) -> RefreshRecord | None:
        """Atomically consume a refresh token.

        Marks the token as used and returns its record.
        Returns ``None`` if the token does not exist, is
        expired, was already consumed (replay detection), or
        belongs to a revoked session.

        Args:
            token_hash: HMAC-SHA256 hash of the presented token.
            is_session_revoked: Optional sync callback (e.g.
                ``SessionStore.is_revoked``) to reject tokens
                whose session has been revoked.

        Returns:
            The token record, or ``None`` on failure.
        """
        dict_row = self._dict_row
        now = datetime.now(UTC)

        # Run the conditional UPDATE and the replay-detection SELECT in
        # the same connection (and therefore the same transactional view
        # under psycopg's implicit transaction per ``async with conn``)
        # so a concurrent ``cleanup_expired`` cannot delete the row
        # between the two queries and lie about the rejection reason.
        async with (
            self._pool.connection() as conn,
            conn.cursor(row_factory=dict_row) as cur,
        ):
            await cur.execute(
                "UPDATE refresh_tokens SET used = TRUE "
                "WHERE token_hash = %s AND used = FALSE "
                "AND expires_at > %s "
                "RETURNING token_hash, session_id, user_id, "
                "expires_at, used, created_at",
                (token_hash, now),
            )
            row = await cur.fetchone()
            replay_row: dict[str, Any] | None = None
            if row is None:
                await cur.execute(
                    "SELECT used FROM refresh_tokens WHERE token_hash = %s",
                    (token_hash,),
                )
                replay_row = await cur.fetchone()

        if row is not None:
            # Revocation check runs outside the transaction on purpose:
            # the callback may consult a separate durable store with
            # its own connection scope.  If the session is revoked
            # concurrently the UPDATE still committed, so a subsequent
            # retry will be rejected as a replay rather than a
            # revocation -- acceptable audit-trail fuzz, security
            # outcome (token rejected) is correct either way.
            if is_session_revoked and is_session_revoked(
                row["session_id"],
            ):
                logger.warning(
                    API_AUTH_REFRESH_REJECTED,
                    reason="session_revoked",
                    session_id=row["session_id"][:8],
                )
                return None
            logger.info(
                API_AUTH_REFRESH_CONSUMED,
                session_id=row["session_id"],
                user_id=row["user_id"],
            )
            return RefreshRecord(
                token_hash=row["token_hash"],
                session_id=row["session_id"],
                user_id=row["user_id"],
                expires_at=row["expires_at"],
                used=bool(row["used"]),
                created_at=row["created_at"],
            )

        if replay_row is not None and replay_row["used"]:
            logger.warning(
                API_AUTH_REFRESH_REJECTED,
                reason="replay_detected",
                token_hash=token_hash[:8],
            )
        else:
            logger.warning(
                API_AUTH_REFRESH_REJECTED,
                reason="not_found_or_expired",
                token_hash=token_hash[:8],
            )
        return None

    async def revoke_by_session(self, session_id: str) -> int:
        """Mark all refresh tokens for a session as used.

        Args:
            session_id: Session ID whose tokens to revoke.

        Returns:
            Number of tokens revoked.
        """
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                "UPDATE refresh_tokens SET used = TRUE "
                "WHERE session_id = %s AND used = FALSE",
                (session_id,),
            )
            count = cur.rowcount
        if count:
            logger.info(
                API_AUTH_REFRESH_REVOKED,
                session_id=session_id,
                revoked=count,
            )
        return count

    async def revoke_by_user(self, user_id: str) -> int:
        """Mark all refresh tokens for a user as used.

        Args:
            user_id: User ID whose tokens to revoke.

        Returns:
            Number of tokens revoked.
        """
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                "UPDATE refresh_tokens SET used = TRUE "
                "WHERE user_id = %s AND used = FALSE",
                (user_id,),
            )
            count = cur.rowcount
        if count:
            logger.info(
                API_AUTH_REFRESH_REVOKED,
                user_id=user_id,
                revoked=count,
            )
        return count

    async def cleanup_expired(self) -> int:
        """Remove expired tokens.

        Used (consumed) tokens are retained until their expiry so
        that replay detection can still identify double-use attempts.

        Returns:
            Number of records removed.
        """
        now = datetime.now(UTC)
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                "DELETE FROM refresh_tokens WHERE expires_at <= %s",
                (now,),
            )
            count = cur.rowcount
        if count:
            logger.info(API_AUTH_REFRESH_CLEANUP, removed=count)
        return count
