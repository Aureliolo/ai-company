"""Hybrid in-memory + SQLite session store.

The in-memory revocation set provides O(1) sync lookups for the
auth middleware hot path.  SQLite provides durability so revocations
survive server restarts.
"""

from datetime import UTC, datetime

import aiosqlite  # noqa: TC002

from synthorg.api.auth.session import Session
from synthorg.api.guards import HumanRole
from synthorg.core.types import NotBlankStr
from synthorg.observability import get_logger
from synthorg.observability.events.api import (
    API_SESSION_CLEANUP,
    API_SESSION_CREATED,
    API_SESSION_REVOKED,
)

logger = get_logger(__name__)


def _row_to_session(row: aiosqlite.Row) -> Session:
    """Deserialize a database row into a ``Session`` model."""
    return Session(
        session_id=NotBlankStr(row["session_id"]),
        user_id=NotBlankStr(row["user_id"]),
        username=NotBlankStr(row["username"]),
        role=HumanRole(row["role"]),
        ip_address=row["ip_address"],
        user_agent=row["user_agent"],
        created_at=datetime.fromisoformat(row["created_at"]),
        last_active_at=datetime.fromisoformat(
            row["last_active_at"],
        ),
        expires_at=datetime.fromisoformat(row["expires_at"]),
        revoked=bool(row["revoked"]),
    )


class SessionStore:
    """Hybrid session store: in-memory index + SQLite persistence.

    The ``is_revoked`` method is synchronous and checks a local
    ``set`` -- it is called on every authenticated request and
    must not block the event loop.

    Args:
        db: Open aiosqlite connection with ``row_factory`` set.
    """

    def __init__(self, db: aiosqlite.Connection) -> None:
        self._db = db
        self._revoked: set[str] = set()

    async def load_revoked(self) -> None:
        """Load revoked session IDs from SQLite into memory.

        Call once at startup to restore revocation state.  Only
        loads sessions that have not yet expired -- expired JWTs
        are rejected by the decoder regardless of revocation.
        """
        now = datetime.now(UTC).isoformat()
        cursor = await self._db.execute(
            "SELECT session_id FROM sessions WHERE revoked = 1 AND expires_at > ?",
            (now,),
        )
        rows = await cursor.fetchall()
        self._revoked = {row["session_id"] for row in rows}

    async def create(self, session: Session) -> None:
        """Persist a new session.

        Args:
            session: Session to persist.
        """
        await self._db.execute(
            "INSERT INTO sessions "
            "(session_id, user_id, username, role, ip_address, "
            "user_agent, created_at, last_active_at, expires_at, "
            "revoked) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                session.session_id,
                session.user_id,
                session.username,
                session.role.value,
                session.ip_address,
                session.user_agent,
                session.created_at.isoformat(),
                session.last_active_at.isoformat(),
                session.expires_at.isoformat(),
                int(session.revoked),
            ),
        )
        await self._db.commit()
        logger.debug(
            API_SESSION_CREATED,
            session_id=session.session_id,
            user_id=session.user_id,
        )

    async def get(self, session_id: str) -> Session | None:
        """Look up a session by ID.

        Args:
            session_id: The JWT ``jti`` claim.

        Returns:
            The session, or ``None`` if not found.
        """
        cursor = await self._db.execute(
            "SELECT * FROM sessions WHERE session_id = ?",
            (session_id,),
        )
        row = await cursor.fetchone()
        return _row_to_session(row) if row else None

    async def list_by_user(
        self,
        user_id: str,
    ) -> tuple[Session, ...]:
        """List active (non-expired, non-revoked) sessions for a user.

        Args:
            user_id: Owner's user ID.

        Returns:
            Sessions ordered by creation time (newest first).
        """
        now = datetime.now(UTC).isoformat()
        cursor = await self._db.execute(
            "SELECT * FROM sessions "
            "WHERE user_id = ? AND revoked = 0 "
            "AND expires_at > ? "
            "ORDER BY created_at DESC",
            (user_id, now),
        )
        rows = await cursor.fetchall()
        return tuple(_row_to_session(r) for r in rows)

    async def list_all(self) -> tuple[Session, ...]:
        """List all active (non-expired, non-revoked) sessions.

        Returns:
            Sessions ordered by creation time (newest first).
        """
        now = datetime.now(UTC).isoformat()
        cursor = await self._db.execute(
            "SELECT * FROM sessions "
            "WHERE revoked = 0 AND expires_at > ? "
            "ORDER BY created_at DESC",
            (now,),
        )
        rows = await cursor.fetchall()
        return tuple(_row_to_session(r) for r in rows)

    async def revoke(self, session_id: str) -> bool:
        """Revoke a session by ID.

        Args:
            session_id: The JWT ``jti`` claim to revoke.

        Returns:
            ``True`` if the session existed and was revoked,
            ``False`` if not found.
        """
        cursor = await self._db.execute(
            "UPDATE sessions SET revoked = 1 WHERE session_id = ? AND revoked = 0",
            (session_id,),
        )
        await self._db.commit()
        if cursor.rowcount > 0:
            self._revoked.add(session_id)
            logger.info(
                API_SESSION_REVOKED,
                session_id=session_id,
            )
            return True
        return False

    async def revoke_all_for_user(self, user_id: str) -> int:
        """Revoke all active sessions for a user.

        After the UPDATE, re-queries to collect all revoked
        session IDs for in-memory set synchronization (the
        UPDATE only returns a count, not the affected IDs).
        Only non-expired sessions are loaded into the
        in-memory set.

        Args:
            user_id: The user whose sessions to revoke.

        Returns:
            Number of sessions revoked.
        """
        now = datetime.now(UTC).isoformat()
        cursor = await self._db.execute(
            "UPDATE sessions SET revoked = 1 "
            "WHERE user_id = ? AND revoked = 0 AND expires_at > ?",
            (user_id, now),
        )
        await self._db.commit()
        count = cursor.rowcount
        if count == 0:
            return 0
        cursor = await self._db.execute(
            "SELECT session_id FROM sessions "
            "WHERE user_id = ? AND revoked = 1 AND expires_at > ?",
            (user_id, now),
        )
        rows = await cursor.fetchall()
        self._revoked.update(row["session_id"] for row in rows)
        logger.info(
            API_SESSION_REVOKED,
            user_id=user_id,
            count=count,
        )
        return count

    def is_revoked(self, session_id: str) -> bool:
        """Check whether a session is revoked (sync, O(1)).

        This is the auth middleware hot-path check.

        Args:
            session_id: The JWT ``jti`` claim.

        Returns:
            ``True`` if the session has been revoked.
        """
        return session_id in self._revoked

    async def cleanup_expired(self) -> int:
        """Remove expired sessions from the database.

        Also clears revocation entries for expired sessions since
        the JWT itself is past expiry and cannot be used.

        Returns:
            Number of sessions removed.
        """
        now = datetime.now(UTC).isoformat()
        # Fetch expired IDs to clean in-memory set.
        cursor = await self._db.execute(
            "SELECT session_id FROM sessions WHERE expires_at <= ?",
            (now,),
        )
        rows = await cursor.fetchall()
        ids = {row["session_id"] for row in rows}
        if not ids:
            return 0

        await self._db.execute(
            "DELETE FROM sessions WHERE expires_at <= ?",
            (now,),
        )
        await self._db.commit()
        self._revoked -= ids
        logger.debug(API_SESSION_CLEANUP, removed=len(ids))
        return len(ids)
