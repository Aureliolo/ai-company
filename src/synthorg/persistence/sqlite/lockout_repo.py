"""SQLite-backed account lockout repository.

Tracks failed login attempts per username and enforces temporary
lockout after exceeding the threshold within a sliding window.  An
in-memory ``{username: monotonic_unlock_time}`` map backs O(1)
synchronous ``is_locked`` checks on the auth hot path.

Single-instance deployment assumption: the cache is process-local,
so horizontally-scaled deployments would see per-node drift.
Multi-instance deployments require a shared lock store.
"""

import threading
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


class SQLiteLockoutRepository:
    """SQLite-backed account lockout repository.

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
        self._locked_lock: threading.Lock = threading.Lock()

    @property
    def lockout_duration_seconds(self) -> int:
        """Return the lockout duration in seconds for Retry-After."""
        return self._duration_seconds

    def is_locked(self, username: str) -> bool:
        """Sync O(1) lockout check for the auth hot path."""
        username = username.lower()
        with self._locked_lock:
            locked_until = self._locked.get(username)
            if locked_until is None:
                return False
            if time.monotonic() > locked_until:
                self._locked.pop(username, None)
                return False
            return True

    async def load_locked(self) -> int:
        """Restore in-memory lockout state from recent failure records."""
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
                uname = row["username"].lower()
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
        """Record a failed login attempt.  Return ``True`` if now locked."""
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
        """Clear failure count on successful login."""
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
        """Remove old attempt records outside all windows."""
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
