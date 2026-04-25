"""SQLite-backed refresh token repository.

Refresh tokens are opaque strings stored as HMAC-SHA256 hashes.
Each token is single-use: consuming it atomically marks it as used
and returns the associated session/user info for re-issuance.
"""

from collections.abc import Callable  # noqa: TC003
from datetime import UTC, datetime

import aiosqlite  # noqa: TC002

from synthorg.api.auth.refresh_record import RefreshRecord
from synthorg.observability import get_logger
from synthorg.observability.events.api import (
    API_AUTH_REFRESH_CLEANUP,
    API_AUTH_REFRESH_CONSUMED,
    API_AUTH_REFRESH_REJECTED,
    API_AUTH_REFRESH_REVOKED,
)

logger = get_logger(__name__)


class SQLiteRefreshTokenRepository:
    """SQLite-backed refresh token repository.

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
        """Store a new refresh token."""
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

    async def consume(
        self,
        token_hash: str,
        *,
        is_session_revoked: Callable[[str], bool] | None = None,
    ) -> RefreshRecord | None:
        """Atomically consume a refresh token (single-use rotation)."""
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
        """Mark all refresh tokens for a session as used."""
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
        """Mark all refresh tokens for a user as used."""
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
        """Remove expired tokens."""
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
