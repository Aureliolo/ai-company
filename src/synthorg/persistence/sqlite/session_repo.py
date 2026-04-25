"""SQLite-backed session repository.

Hybrid in-memory + durable session store.  The in-memory revocation
set provides O(1) sync lookups for the auth middleware hot path; the
SQLite connection provides survival across restarts.
"""

import datetime as _datetime_mod
from datetime import UTC, datetime
from typing import Any

import aiosqlite  # noqa: TC002

from synthorg.api.auth.session import Session
from synthorg.api.guards import HumanRole
from synthorg.core.types import NotBlankStr
from synthorg.observability import get_logger
from synthorg.observability.events.api import (
    API_SESSION_CLEANUP,
    API_SESSION_LIMIT_ENFORCED,
    API_SESSION_REVOKED,
)

logger = get_logger(__name__)


def _coerce_datetime(value: Any) -> datetime:
    """Accept a pre-parsed ``datetime`` or an ISO-8601 string.

    SQLite stores timestamps as TEXT; aiosqlite returns them as ``str``.
    The isinstance check resolves ``datetime.datetime`` via the stdlib
    module reference rather than the bound ``datetime`` name because
    tests patch the latter with a ``MagicMock``.
    """
    if isinstance(value, _datetime_mod.datetime):
        return value
    return datetime.fromisoformat(value)


def _row_to_session(row: Any) -> Session:
    """Deserialize an aiosqlite.Row into a :class:`Session`."""
    return Session(
        session_id=NotBlankStr(row["session_id"]),
        user_id=NotBlankStr(row["user_id"]),
        username=NotBlankStr(row["username"]),
        role=HumanRole(row["role"]),
        ip_address=row["ip_address"],
        user_agent=row["user_agent"],
        created_at=_coerce_datetime(row["created_at"]),
        last_active_at=_coerce_datetime(row["last_active_at"]),
        expires_at=_coerce_datetime(row["expires_at"]),
        revoked=bool(row["revoked"]),
    )


class SQLiteSessionRepository:
    """SQLite-backed hybrid session repository.

    The ``is_revoked`` method is synchronous and checks a local ``set``
    -- it is called on every authenticated request and must not block
    the event loop.

    Args:
        db: Open aiosqlite connection with ``row_factory`` set.
    """

    def __init__(self, db: aiosqlite.Connection) -> None:
        self._db = db
        self._revoked: set[str] = set()

    async def load_revoked(self) -> None:
        """Load revoked session IDs from SQLite into memory.

        Called once at startup to restore revocation state.  Only
        loads sessions that have not yet expired -- expired JWTs are
        rejected by the decoder regardless of revocation.
        """
        now = datetime.now(UTC).isoformat()
        cursor = await self._db.execute(
            "SELECT session_id FROM sessions WHERE revoked = 1 AND expires_at > ?",
            (now,),
        )
        rows = await cursor.fetchall()
        self._revoked = {row["session_id"] for row in rows}

    async def create(self, session: Session) -> None:
        """Persist a new session."""
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
        if session.revoked:
            self._revoked.add(session.session_id)

    async def get(self, session_id: str) -> Session | None:
        """Look up a session by ID."""
        cursor = await self._db.execute(
            "SELECT * FROM sessions WHERE session_id = ?",
            (session_id,),
        )
        row = await cursor.fetchone()
        return _row_to_session(row) if row else None

    async def list_by_user(self, user_id: str) -> tuple[Session, ...]:
        """List active (non-expired, non-revoked) sessions for a user."""
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
        """List all active (non-expired, non-revoked) sessions."""
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
        """Revoke a session by ID."""
        cursor = await self._db.execute(
            "UPDATE sessions SET revoked = 1 WHERE session_id = ? AND revoked = 0",
            (session_id,),
        )
        await self._db.commit()
        if cursor.rowcount > 0:
            self._revoked.add(session_id)
            logger.info(API_SESSION_REVOKED, session_id=session_id)
            return True
        return False

    async def revoke_all_for_user(self, user_id: str) -> int:
        """Revoke all active sessions for a user."""
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
        logger.info(API_SESSION_REVOKED, user_id=user_id, count=count)
        return count

    async def enforce_session_limit(
        self,
        user_id: str,
        max_sessions: int,
    ) -> int:
        """Revoke oldest sessions if user exceeds the concurrent limit."""
        if max_sessions <= 0:
            return 0
        active = await self.list_by_user(user_id)
        excess = len(active) - max_sessions
        if excess <= 0:
            return 0
        to_revoke = active[-excess:]
        revoked = 0
        for session in to_revoke:
            if await self.revoke(session.session_id):
                revoked += 1
        if revoked:
            logger.info(
                API_SESSION_LIMIT_ENFORCED,
                user_id=user_id,
                revoked=revoked,
                max_sessions=max_sessions,
            )
        return revoked

    def is_revoked(self, session_id: str) -> bool:
        """Check whether a session is revoked (sync, O(1))."""
        return session_id in self._revoked

    async def cleanup_expired(self) -> int:
        """Remove expired sessions from the database."""
        now = datetime.now(UTC).isoformat()
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
