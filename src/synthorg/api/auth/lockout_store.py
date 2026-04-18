"""Account lockout store -- hybrid in-memory + SQLite/Postgres.

Tracks failed login attempts per username and enforces
temporary lockout after exceeding the configured threshold
within a sliding time window.

The ``is_locked`` method is synchronous (O(1) dict lookup)
for use in the login hot path without blocking the event loop.
Access to the in-memory ``_locked`` dict is guarded by a
``threading.Lock`` so concurrent event-loop tasks (and any
embedded sync callers) see a consistent view when the dict is
mutated by ``record_failure`` / ``record_success``.

The public surface is the :class:`LockoutStore` protocol; two
concrete implementations back it:

* :class:`SqliteLockoutStore` -- wraps an ``aiosqlite.Connection``.
* :class:`PostgresLockoutStore` -- wraps a
  ``psycopg_pool.AsyncConnectionPool``.

Lifecycle code picks the concrete class that matches the active
persistence backend (see ``synthorg.api.lifecycle``).

**Deployment assumption:** these stores are **single-instance only**.
The ``_locked`` cache is process-local, so horizontally-scaled
deployments would see per-node drift: a lockout recorded on node A
is invisible to node B until B records its own failure for the same
username.  Multi-instance deployments require a shared lock store
(Redis, DB-authoritative ``is_locked`` query, or the like); that
work is out of scope for the initial release and tracked as a
follow-up.  Callers that share a process (single ASGI worker,
multiple concurrent tasks) are the supported configuration.

**Pool lifecycle:** both stores receive the connection handle from
the caller and never close it.  ``SqliteLockoutStore`` composes on
an ``aiosqlite.Connection`` and ``PostgresLockoutStore`` on an
``AsyncConnectionPool``.  The caller owns the handle for the whole
application lifetime and must outlive the store; callers must not
close the pool while store operations may still be in flight.
"""

import threading
import time
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

import aiosqlite  # noqa: TC002

from synthorg.api.auth.config import AuthConfig  # noqa: TC001
from synthorg.observability import get_logger
from synthorg.observability.events.api import (
    API_AUTH_ACCOUNT_LOCKED,
    API_AUTH_LOCKOUT_CLEANUP,
    API_AUTH_LOCKOUT_CLEARED,
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


class _InMemoryLockoutCacheMixin:
    """Shared in-memory lockout-cache behaviour.

    Both :class:`SqliteLockoutStore` and :class:`PostgresLockoutStore`
    wrap a persistent backend but keep a process-local
    ``{username: monotonic_unlock_time}`` map for O(1) synchronous
    ``is_locked`` checks on the auth hot path.  This mixin hosts the
    single implementation so both concrete stores stay in sync; each
    concrete store owns the ``_locked`` dict and its guarding
    :class:`threading.Lock` (set in ``__init__``).
    """

    _locked: dict[str, float]
    _locked_lock: threading.Lock

    def is_locked(self, username: str) -> bool:
        """Check if an account is locked (sync, O(1)).

        Called on every login attempt -- must not block.  Reads only
        the process-local cache; see the module docstring for the
        single-instance deployment caveat.

        Args:
            username: Login username to check.

        Returns:
            ``True`` if the account is currently locked.
        """
        username = username.lower()
        with self._locked_lock:
            locked_until = self._locked.get(username)
            if locked_until is None:
                return False
            if time.monotonic() > locked_until:
                self._locked.pop(username, None)
                return False
            return True


@runtime_checkable
class LockoutStore(Protocol):
    """Public contract every lockout-store backend must satisfy.

    All methods are async except :meth:`is_locked`, which hits the
    in-memory dict and must not block the event loop (auth middleware
    hot path).  Concrete implementations ship the state they need
    (cache dict, threshold, window, duration) as private attributes;
    callers only depend on the public methods and
    :attr:`lockout_duration_seconds`.
    """

    async def load_locked(self) -> int:
        """Restore in-memory lockout state from database."""
        ...

    async def record_failure(
        self,
        username: str,
        ip_address: str = "",
    ) -> bool:
        """Record a failed login attempt; return True if now locked."""
        ...

    async def record_success(self, username: str) -> None:
        """Clear failure count on successful login."""
        ...

    async def cleanup_expired(self) -> int:
        """Remove old attempt records; return count removed."""
        ...

    def is_locked(self, username: str) -> bool:
        """Synchronous, O(1) lockout check for the auth hot path."""
        ...

    @property
    def lockout_duration_seconds(self) -> int:
        """Return the lockout duration in seconds for Retry-After."""
        ...


class SqliteLockoutStore(_InMemoryLockoutCacheMixin):
    """SQLite-backed account lockout store.

    Tracks failed login attempts per username and enforces
    temporary lockout after exceeding the threshold within a window.
    The in-memory lockout dict is O(1) for the auth hot path;
    :meth:`is_locked` is inherited from :class:`_InMemoryLockoutCacheMixin`.

    Args:
        db: Open aiosqlite connection with ``row_factory`` set.
        config: Auth configuration with lockout thresholds.
    """

    def __init__(
        self,
        db: aiosqlite.Connection,
        config: AuthConfig,
    ) -> None:
        self._db = db
        self._threshold = config.lockout_threshold
        self._window = timedelta(minutes=config.lockout_window_minutes)
        self._duration = timedelta(minutes=config.lockout_duration_minutes)
        self._duration_seconds = config.lockout_duration_minutes * 60
        self._locked: dict[str, float] = {}
        # ``is_locked`` is sync and runs on the hot path, so we cannot
        # use ``asyncio.Lock``.  ``threading.Lock`` is GIL-friendly and
        # fast enough for the low-contention access pattern; it keeps
        # the sync expiry-pop atomic vs concurrent ``record_failure`` /
        # ``record_success`` writes.
        self._locked_lock: threading.Lock = threading.Lock()

    @property
    def lockout_duration_seconds(self) -> int:
        """Return the lockout duration in seconds for Retry-After."""
        return self._duration_seconds

    async def load_locked(self) -> int:
        """Restore in-memory lockout state from recent failure records.

        Queries the database for usernames that have accumulated
        enough failures within the sliding window to be locked.
        Called once at startup so that lockout survives restarts.
        The SQL aggregates within the lockout window -- bounded by
        the number of distinct locked usernames in that window, not
        by the full history -- so no explicit timeout is required
        for the typical deployment size.  Operators with very large
        ``login_attempts`` tables should prune via ``cleanup_expired``
        on a schedule; the sliding-window ``WHERE`` clause keeps this
        query from degenerating into a full table scan.

        Returns:
            Number of accounts restored to locked state.
        """
        now = datetime.now(UTC)
        window_start = (now - self._window).isoformat()
        cursor = await self._db.execute(
            "SELECT username, COUNT(*) AS cnt, "
            "MAX(attempted_at) AS max_attempted_at "
            "FROM login_attempts "
            "WHERE attempted_at >= ? "
            "GROUP BY username "
            "HAVING cnt >= ?",
            (window_start, self._threshold),
        )
        rows = await cursor.fetchall()
        mono_now = time.monotonic()
        restored = 0
        with self._locked_lock:
            for row in rows:
                uname = row["username"]
                uname = uname.lower()
                if uname not in self._locked:
                    max_at = datetime.fromisoformat(
                        row["max_attempted_at"],
                    )
                    locked_until = max_at + self._duration
                    remaining = (locked_until - now).total_seconds()
                    if remaining > 0:
                        self._locked[uname] = mono_now + remaining
                        restored += 1
        if restored:
            logger.info(
                API_AUTH_ACCOUNT_LOCKED,
                note="Restored lockout state from database",
                restored=restored,
            )
        return restored

    async def record_failure(
        self,
        username: str,
        ip_address: str = "",
    ) -> bool:
        """Record a failed login attempt.

        Inserts the attempt into SQLite, then counts recent
        attempts within the sliding window.  The INSERT and SELECT
        run inside a single ``BEGIN IMMEDIATE`` transaction so a
        concurrent ``cleanup_expired`` cannot delete rows between
        write and count -- that race could otherwise leave the
        account marked locked with a stale, below-threshold count.

        Args:
            username: Login username.
            ip_address: Client IP address.

        Returns:
            ``True`` if the account is now locked.
        """
        username = username.lower()
        now = datetime.now(UTC)
        window_start = (now - self._window).isoformat()
        await self._db.execute("BEGIN IMMEDIATE")
        try:
            await self._db.execute(
                "INSERT INTO login_attempts "
                "(username, attempted_at, ip_address) "
                "VALUES (?, ?, ?)",
                (username, now.isoformat(), ip_address),
            )
            cursor = await self._db.execute(
                "SELECT COUNT(*) FROM login_attempts "
                "WHERE username = ? AND attempted_at >= ?",
                (username, window_start),
            )
            row = await cursor.fetchone()
            await self._db.commit()
        except BaseException:
            await self._db.rollback()
            raise
        count = row[0] if row else 0

        if count >= self._threshold:
            with self._locked_lock:
                self._locked[username] = time.monotonic() + self._duration_seconds
            logger.warning(
                API_AUTH_ACCOUNT_LOCKED,
                username=username,
                attempts=count,
                threshold=self._threshold,
                duration_minutes=self._duration.total_seconds() / 60,
            )
            return True
        return False

    async def record_success(self, username: str) -> None:
        """Clear failure count on successful login.

        Removes all attempt records for the username and
        clears the in-memory lock.

        Args:
            username: Login username.
        """
        username = username.lower()
        await self._db.execute(
            "DELETE FROM login_attempts WHERE username = ?",
            (username,),
        )
        await self._db.commit()
        with self._locked_lock:
            was_locked = self._locked.pop(username, None) is not None
        if was_locked:
            logger.info(
                API_AUTH_LOCKOUT_CLEARED,
                username=username,
            )

    async def cleanup_expired(self) -> int:
        """Remove old attempt records outside all windows.

        Removes records older than ``2 * window`` to keep
        the table bounded.

        Returns:
            Number of records removed.
        """
        cutoff = (datetime.now(UTC) - self._window * 2).isoformat()
        cursor = await self._db.execute(
            "DELETE FROM login_attempts WHERE attempted_at < ?",
            (cutoff,),
        )
        await self._db.commit()
        count = cursor.rowcount
        if count:
            logger.debug(
                API_AUTH_LOCKOUT_CLEANUP,
                removed=count,
            )
        return count


class PostgresLockoutStore(_InMemoryLockoutCacheMixin):
    """Postgres-backed account lockout store.

    Uses the shared ``AsyncConnectionPool`` (same one every
    Postgres repository composes against). Each operation checks
    out a connection via ``async with pool.connection() as conn``;
    the context manager auto-commits the transaction on a clean
    exit and rolls back on exception, so no explicit ``commit()``
    call is required.  :meth:`is_locked` is inherited from
    :class:`_InMemoryLockoutCacheMixin`.

    Args:
        pool: An open ``psycopg_pool.AsyncConnectionPool``.
        config: Auth configuration with lockout thresholds.
    """

    def __init__(
        self,
        pool: AsyncConnectionPool,
        config: AuthConfig,
    ) -> None:
        self._pool = pool
        self._threshold = config.lockout_threshold
        self._window = timedelta(minutes=config.lockout_window_minutes)
        self._duration = timedelta(minutes=config.lockout_duration_minutes)
        self._duration_seconds = config.lockout_duration_minutes * 60
        self._locked: dict[str, float] = {}
        self._locked_lock: threading.Lock = threading.Lock()
        self._dict_row = _import_dict_row()

    @property
    def lockout_duration_seconds(self) -> int:
        """Return the lockout duration in seconds for Retry-After."""
        return self._duration_seconds

    async def load_locked(self) -> int:
        """Restore in-memory lockout state from recent failure records.

        Queries the database for usernames that have accumulated
        enough failures within the sliding window to be locked.
        Called once at startup so that lockout survives restarts.

        Returns:
            Number of accounts restored to locked state.
        """
        dict_row = self._dict_row

        now = datetime.now(UTC)
        window_start = now - self._window
        async with (
            self._pool.connection() as conn,
            conn.cursor(row_factory=dict_row) as cur,
        ):
            await cur.execute(
                "SELECT username, COUNT(*) AS cnt, "
                "MAX(attempted_at) AS max_attempted_at "
                "FROM login_attempts "
                "WHERE attempted_at >= %s "
                "GROUP BY username "
                "HAVING COUNT(*) >= %s",
                (window_start, self._threshold),
            )
            rows = await cur.fetchall()

        mono_now = time.monotonic()
        restored = 0
        with self._locked_lock:
            for row in rows:
                uname = row["username"]
                uname = uname.lower()
                if uname not in self._locked:
                    max_at = row["max_attempted_at"]
                    locked_until = max_at + self._duration
                    remaining = (locked_until - now).total_seconds()
                    if remaining > 0:
                        self._locked[uname] = mono_now + remaining
                        restored += 1
        if restored:
            logger.info(
                API_AUTH_ACCOUNT_LOCKED,
                note="Restored lockout state from database",
                restored=restored,
            )
        return restored

    async def record_failure(
        self,
        username: str,
        ip_address: str = "",
    ) -> bool:
        """Record a failed login attempt.

        Inserts the attempt into Postgres, then counts recent
        attempts within the sliding window.  INSERT + COUNT share a
        single ``async with conn`` scope (one psycopg implicit
        transaction) so a concurrent ``cleanup_expired`` cannot
        delete rows between write and count -- that race would
        otherwise leave the account locked with a stale count.

        Args:
            username: Login username.
            ip_address: Client IP address.

        Returns:
            ``True`` if the account is now locked.
        """
        username = username.lower()
        now = datetime.now(UTC)
        window_start = now - self._window

        async with (
            self._pool.connection() as conn,
            conn.transaction(),
            conn.cursor() as cur,
        ):
            await cur.execute(
                "INSERT INTO login_attempts "
                "(username, attempted_at, ip_address) "
                "VALUES (%s, %s, %s)",
                (username, now, ip_address),
            )
            await cur.execute(
                "SELECT COUNT(*) FROM login_attempts "
                "WHERE username = %s AND attempted_at >= %s",
                (username, window_start),
            )
            row = await cur.fetchone()

        count = row[0] if row else 0
        if count >= self._threshold:
            with self._locked_lock:
                self._locked[username] = time.monotonic() + self._duration_seconds
            logger.warning(
                API_AUTH_ACCOUNT_LOCKED,
                username=username,
                attempts=count,
                threshold=self._threshold,
                duration_minutes=self._duration.total_seconds() / 60,
            )
            return True
        return False

    async def record_success(self, username: str) -> None:
        """Clear failure count on successful login.

        Removes all attempt records for the username and
        clears the in-memory lock.

        Args:
            username: Login username.
        """
        username = username.lower()
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                "DELETE FROM login_attempts WHERE username = %s",
                (username,),
            )
        with self._locked_lock:
            was_locked = self._locked.pop(username, None) is not None
        if was_locked:
            logger.info(
                API_AUTH_LOCKOUT_CLEARED,
                username=username,
            )

    async def cleanup_expired(self) -> int:
        """Remove old attempt records outside all windows.

        Removes records older than ``2 * window`` to keep
        the table bounded.

        Returns:
            Number of records removed.
        """
        cutoff = datetime.now(UTC) - self._window * 2
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                "DELETE FROM login_attempts WHERE attempted_at < %s",
                (cutoff,),
            )
            count = cur.rowcount
        if count:
            logger.debug(
                API_AUTH_LOCKOUT_CLEANUP,
                removed=count,
            )
        return count
