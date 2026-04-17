"""Hybrid in-memory + durable session store.

The in-memory revocation set provides O(1) sync lookups for the
auth middleware hot path.  A durable backend (SQLite or Postgres)
provides survival across restarts.

The public surface is the :class:`SessionStore` protocol; two
concrete implementations back it:

* :class:`SqliteSessionStore` -- wraps an ``aiosqlite.Connection``.
* :class:`PostgresSessionStore` -- wraps a
  ``psycopg_pool.AsyncConnectionPool`` so it composes with the
  shared Postgres backend without holding a dedicated connection.

Lifecycle code picks the concrete class that matches the active
persistence backend (see ``synthorg.api.lifecycle``).
"""

import datetime as _datetime_mod
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

import aiosqlite  # noqa: TC002

from synthorg.api.auth.session import Session
from synthorg.api.guards import HumanRole
from synthorg.core.types import NotBlankStr
from synthorg.observability import get_logger
from synthorg.observability.events.api import (
    API_SESSION_CLEANUP,
    API_SESSION_CREATED,
    API_SESSION_LIMIT_ENFORCED,
    API_SESSION_REVOKED,
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


def _coerce_datetime(value: Any) -> datetime:
    """Accept a pre-parsed ``datetime`` or an ISO-8601 string and return a ``datetime``.

    SQLite stores timestamps as TEXT; aiosqlite returns them as ``str``.
    Postgres stores ``TIMESTAMPTZ``; psycopg returns them already parsed
    as ``datetime``. The session store is backend-agnostic, so this
    helper normalises both without hiding schema-level type drift
    behind a blanket ``str()`` cast.

    The isinstance check resolves ``datetime.datetime`` via the stdlib
    module reference rather than the ``from datetime import datetime``
    binding because tests patch the latter with a ``MagicMock`` to
    freeze ``datetime.now``; that mock is not a valid ``isinstance``
    second argument.
    """
    if isinstance(value, _datetime_mod.datetime):
        return value
    return datetime.fromisoformat(value)


def _row_to_session(row: Any) -> Session:
    """Deserialize a database row into a ``Session`` model.

    Accepts any mapping-like row (aiosqlite.Row, psycopg dict_row).
    """
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


@runtime_checkable
class SessionStore(Protocol):
    """Session store contract implemented by SQLite and Postgres backends.

    All methods are async except :meth:`is_revoked`, which hits the
    in-memory set and must not block the event loop (auth middleware
    hot path). Method docstrings on this protocol describe the
    contract; concrete implementations reuse the same semantics.

    Attributes:
        _revoked: In-memory cache of revoked session IDs. Part of
            the protocol so test fixtures can clear it between tests
            without casting to a concrete implementation.
    """

    _revoked: set[str]

    async def load_revoked(self) -> None:
        """Load revoked session IDs from durable storage into memory."""
        ...

    async def create(self, session: Session) -> None:
        """Persist a new session."""
        ...

    async def get(self, session_id: str) -> Session | None:
        """Look up a session by ID, or return ``None`` if missing."""
        ...

    async def list_by_user(self, user_id: str) -> tuple[Session, ...]:
        """List active (non-expired, non-revoked) sessions for a user."""
        ...

    async def list_all(self) -> tuple[Session, ...]:
        """List all active (non-expired, non-revoked) sessions."""
        ...

    async def revoke(self, session_id: str) -> bool:
        """Revoke a session by ID; return ``True`` if it existed."""
        ...

    async def revoke_all_for_user(self, user_id: str) -> int:
        """Revoke every active session for a user; return the count."""
        ...

    async def enforce_session_limit(
        self,
        user_id: str,
        max_sessions: int,
    ) -> int:
        """Revoke oldest sessions when a user exceeds the concurrent limit."""
        ...

    def is_revoked(self, session_id: str) -> bool:
        """Synchronous, O(1) revocation check for the auth hot path."""
        ...

    async def cleanup_expired(self) -> int:
        """Remove expired sessions from durable storage; return count."""
        ...


class SqliteSessionStore:
    """SQLite-backed hybrid session store.

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
            # Keep the in-memory revocation cache consistent with the
            # persisted row so ``is_revoked()`` reports the correct
            # state without waiting for the next ``load_revoked()``.
            self._revoked.add(session.session_id)
        logger.debug(
            API_SESSION_CREATED,
            session_id=session.session_id,
            user_id=session.user_id,
        )

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


class PostgresSessionStore:
    """Postgres-backed hybrid session store.

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
        self._revoked: set[str] = set()
        self._dict_row = _import_dict_row()

    async def load_revoked(self) -> None:
        """Load revoked session IDs from Postgres into memory."""
        dict_row = self._dict_row

        now = datetime.now(UTC)
        async with (
            self._pool.connection() as conn,
            conn.cursor(row_factory=dict_row) as cur,
        ):
            # Pass the timezone-aware ``datetime`` directly; psycopg
            # adapts it to ``TIMESTAMPTZ`` natively, which avoids the
            # ISO-string round-trip and keeps the comparison in the
            # column's native type.
            await cur.execute(
                "SELECT session_id FROM sessions "
                "WHERE revoked = TRUE AND expires_at > %s",
                (now,),
            )
            rows = await cur.fetchall()
        self._revoked = {row["session_id"] for row in rows}

    async def create(self, session: Session) -> None:
        """Persist a new session."""
        # Pass ``datetime`` objects directly so psycopg adapts them to
        # ``TIMESTAMPTZ`` natively, matching the column type and keeping
        # binds consistent with the other methods on this class.
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                "INSERT INTO sessions "
                "(session_id, user_id, username, role, ip_address, "
                "user_agent, created_at, last_active_at, expires_at, "
                "revoked) VALUES "
                "(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    session.session_id,
                    session.user_id,
                    session.username,
                    session.role.value,
                    session.ip_address,
                    session.user_agent,
                    session.created_at,
                    session.last_active_at,
                    session.expires_at,
                    session.revoked,
                ),
            )
        if session.revoked:
            # Mirror the persisted revoked flag into the in-memory cache;
            # otherwise ``is_revoked()`` reports False until the next
            # ``load_revoked()`` pass.
            self._revoked.add(session.session_id)
        logger.debug(
            API_SESSION_CREATED,
            session_id=session.session_id,
            user_id=session.user_id,
        )

    async def get(self, session_id: str) -> Session | None:
        """Look up a session by ID."""
        dict_row = self._dict_row

        async with (
            self._pool.connection() as conn,
            conn.cursor(row_factory=dict_row) as cur,
        ):
            await cur.execute(
                "SELECT * FROM sessions WHERE session_id = %s",
                (session_id,),
            )
            row = await cur.fetchone()
        return _row_to_session(row) if row else None

    async def list_by_user(self, user_id: str) -> tuple[Session, ...]:
        """List active (non-expired, non-revoked) sessions for a user."""
        dict_row = self._dict_row

        now = datetime.now(UTC)
        async with (
            self._pool.connection() as conn,
            conn.cursor(row_factory=dict_row) as cur,
        ):
            await cur.execute(
                "SELECT * FROM sessions "
                "WHERE user_id = %s AND revoked = FALSE "
                "AND expires_at > %s "
                "ORDER BY created_at DESC",
                (user_id, now),
            )
            rows = await cur.fetchall()
        return tuple(_row_to_session(r) for r in rows)

    async def list_all(self) -> tuple[Session, ...]:
        """List all active (non-expired, non-revoked) sessions."""
        dict_row = self._dict_row

        now = datetime.now(UTC)
        async with (
            self._pool.connection() as conn,
            conn.cursor(row_factory=dict_row) as cur,
        ):
            await cur.execute(
                "SELECT * FROM sessions "
                "WHERE revoked = FALSE AND expires_at > %s "
                "ORDER BY created_at DESC",
                (now,),
            )
            rows = await cur.fetchall()
        return tuple(_row_to_session(r) for r in rows)

    async def revoke(self, session_id: str) -> bool:
        """Revoke a session by ID."""
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                "UPDATE sessions SET revoked = TRUE "
                "WHERE session_id = %s AND revoked = FALSE",
                (session_id,),
            )
            count = cur.rowcount
        if count > 0:
            self._revoked.add(session_id)
            logger.info(API_SESSION_REVOKED, session_id=session_id)
            return True
        return False

    async def revoke_all_for_user(self, user_id: str) -> int:
        """Revoke all active sessions for a user."""
        dict_row = self._dict_row

        now = datetime.now(UTC)
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "UPDATE sessions SET revoked = TRUE "
                    "WHERE user_id = %s AND revoked = FALSE "
                    "AND expires_at > %s",
                    (user_id, now),
                )
                count = cur.rowcount
            if count == 0:
                return 0
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    "SELECT session_id FROM sessions "
                    "WHERE user_id = %s AND revoked = TRUE "
                    "AND expires_at > %s",
                    (user_id, now),
                )
                rows = await cur.fetchall()
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
        dict_row = self._dict_row

        now = datetime.now(UTC)
        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    "SELECT session_id FROM sessions WHERE expires_at <= %s",
                    (now,),
                )
                rows = await cur.fetchall()
            ids = {row["session_id"] for row in rows}
            if not ids:
                return 0
            async with conn.cursor() as cur:
                await cur.execute(
                    "DELETE FROM sessions WHERE expires_at <= %s",
                    (now,),
                )
        self._revoked -= ids
        logger.debug(API_SESSION_CLEANUP, removed=len(ids))
        return len(ids)
