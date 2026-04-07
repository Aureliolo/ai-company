"""Account lockout store -- hybrid in-memory + SQLite.

Tracks failed login attempts per username and enforces
temporary lockout after exceeding the configured threshold
within a sliding time window.

The ``is_locked`` method is synchronous (O(1) dict lookup)
for use in the login hot path without blocking the event loop.
"""

import time
from datetime import UTC, datetime, timedelta

import aiosqlite  # noqa: TC002

from synthorg.api.auth.config import AuthConfig  # noqa: TC001
from synthorg.observability import get_logger
from synthorg.observability.events.api import (
    API_AUTH_ACCOUNT_LOCKED,
    API_AUTH_LOCKOUT_CLEANUP,
    API_AUTH_LOCKOUT_CLEARED,
)

logger = get_logger(__name__)


class LockoutStore:
    """Track failed login attempts and account lockout state.

    SQLite records individual login attempts; in-memory lockout
    state is restored from the database at startup via
    ``load_locked()``.

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
        # In-memory cache: {username: locked_until_monotonic}
        self._locked: dict[str, float] = {}

    def is_locked(self, username: str) -> bool:
        """Check if an account is locked (sync, O(1)).

        Called on every login attempt -- must not block.

        Args:
            username: Login username to check.

        Returns:
            ``True`` if the account is currently locked.
        """
        username = username.lower()
        locked_until = self._locked.get(username)
        if locked_until is None:
            return False
        if time.monotonic() > locked_until:
            self._locked.pop(username, None)
            return False
        return True

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
        attempts within the sliding window.  If the count
        reaches the threshold, the account is locked.

        Args:
            username: Login username.
            ip_address: Client IP address.

        Returns:
            ``True`` if the account is now locked.
        """
        username = username.lower()
        now = datetime.now(UTC)
        await self._db.execute(
            "INSERT INTO login_attempts "
            "(username, attempted_at, ip_address) "
            "VALUES (?, ?, ?)",
            (username, now.isoformat(), ip_address),
        )
        await self._db.commit()

        window_start = (now - self._window).isoformat()
        cursor = await self._db.execute(
            "SELECT COUNT(*) FROM login_attempts "
            "WHERE username = ? AND attempted_at >= ?",
            (username, window_start),
        )
        row = await cursor.fetchone()
        count = row[0] if row else 0

        if count >= self._threshold:
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
        if self._locked.pop(username, None) is not None:
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
