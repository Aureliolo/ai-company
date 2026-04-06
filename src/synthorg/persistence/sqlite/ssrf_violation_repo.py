"""SQLite repository implementation for SSRF violation records."""

import sqlite3
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import aiosqlite

from synthorg.observability import get_logger
from synthorg.observability.events.persistence import (
    PERSISTENCE_SSRF_VIOLATION_QUERY_FAILED,
    PERSISTENCE_SSRF_VIOLATION_SAVE_FAILED,
    PERSISTENCE_SSRF_VIOLATION_SAVED,
)
from synthorg.persistence.errors import DuplicateRecordError, PersistenceError
from synthorg.security.ssrf_violation import SsrfViolation, SsrfViolationStatus

if TYPE_CHECKING:
    from synthorg.core.types import NotBlankStr

logger = get_logger(__name__)

_COLS = (
    "id, timestamp, url, hostname, port, resolved_ip, "
    "blocked_range, provider_name, status, resolved_by, resolved_at"
)


class SQLiteSsrfViolationRepository:
    """SQLite implementation of the SsrfViolationRepository protocol.

    Args:
        db: An open aiosqlite connection.
    """

    def __init__(self, db: aiosqlite.Connection) -> None:
        self._db = db

    async def save(self, violation: SsrfViolation) -> None:
        """Persist a new SSRF violation.

        Args:
            violation: The violation to save.

        Raises:
            DuplicateRecordError: If a violation with the same ID exists.
            PersistenceError: If the save fails.
        """
        ts_utc = violation.timestamp.astimezone(UTC).isoformat()
        resolved_at_utc = (
            violation.resolved_at.astimezone(UTC).isoformat()
            if violation.resolved_at
            else None
        )

        try:
            await self._db.execute(
                f"INSERT INTO ssrf_violations ({_COLS}) "  # noqa: S608
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    violation.id,
                    ts_utc,
                    violation.url,
                    violation.hostname,
                    violation.port,
                    violation.resolved_ip,
                    violation.blocked_range,
                    violation.provider_name,
                    violation.status.value,
                    violation.resolved_by,
                    resolved_at_utc,
                ),
            )
            await self._db.commit()
        except sqlite3.IntegrityError as exc:
            if "UNIQUE" in str(exc):
                msg = f"SSRF violation {violation.id!r} already exists"
                raise DuplicateRecordError(msg) from exc
            msg = f"Failed to save SSRF violation: {exc}"
            logger.exception(PERSISTENCE_SSRF_VIOLATION_SAVE_FAILED, error=msg)
            raise PersistenceError(msg) from exc
        except (sqlite3.Error, aiosqlite.Error) as exc:
            msg = f"Failed to save SSRF violation: {exc}"
            logger.exception(PERSISTENCE_SSRF_VIOLATION_SAVE_FAILED, error=msg)
            raise PersistenceError(msg) from exc
        else:
            logger.debug(
                PERSISTENCE_SSRF_VIOLATION_SAVED,
                id=violation.id,
            )

    async def get(
        self,
        violation_id: NotBlankStr,
    ) -> SsrfViolation | None:
        """Retrieve a violation by ID.

        Args:
            violation_id: The violation identifier.

        Returns:
            The violation, or None if not found.
        """
        try:
            cursor = await self._db.execute(
                f"SELECT {_COLS} FROM ssrf_violations WHERE id = ?",  # noqa: S608
                (violation_id,),
            )
            row = await cursor.fetchone()
        except (sqlite3.Error, aiosqlite.Error) as exc:
            msg = f"Failed to get SSRF violation: {exc}"
            logger.exception(PERSISTENCE_SSRF_VIOLATION_QUERY_FAILED, error=msg)
            raise PersistenceError(msg) from exc

        if row is None:
            return None
        return _row_to_violation(row)

    async def list_violations(
        self,
        *,
        status: SsrfViolationStatus | None = None,
        limit: int = 100,
    ) -> tuple[SsrfViolation, ...]:
        """List violations, optionally filtered by status.

        Args:
            status: Filter by status (None for all).
            limit: Maximum number of results.

        Returns:
            Tuple of violations, ordered by timestamp DESC.
        """
        if status is not None:
            query = (
                f"SELECT {_COLS} FROM ssrf_violations "  # noqa: S608
                "WHERE status = ? ORDER BY timestamp DESC LIMIT ?"
            )
            params: tuple[Any, ...] = (status.value, limit)
        else:
            query = (
                f"SELECT {_COLS} FROM ssrf_violations "  # noqa: S608
                "ORDER BY timestamp DESC LIMIT ?"
            )
            params = (limit,)

        try:
            cursor = await self._db.execute(query, params)
            rows = await cursor.fetchall()
        except (sqlite3.Error, aiosqlite.Error) as exc:
            msg = f"Failed to list SSRF violations: {exc}"
            logger.exception(PERSISTENCE_SSRF_VIOLATION_QUERY_FAILED, error=msg)
            raise PersistenceError(msg) from exc

        return tuple(_row_to_violation(row) for row in rows)

    async def update_status(
        self,
        violation_id: NotBlankStr,
        *,
        status: SsrfViolationStatus,
        resolved_by: NotBlankStr,
        resolved_at: datetime,
    ) -> bool:
        """Update a violation's status.

        Args:
            violation_id: The violation to update.
            status: New status.
            resolved_by: User who resolved it.
            resolved_at: When it was resolved.

        Returns:
            True if the violation was found and updated.
        """
        resolved_at_utc = resolved_at.astimezone(UTC).isoformat()
        try:
            cursor = await self._db.execute(
                "UPDATE ssrf_violations "
                "SET status = ?, resolved_by = ?, resolved_at = ? "
                "WHERE id = ? AND status = 'pending'",
                (status.value, resolved_by, resolved_at_utc, violation_id),
            )
            await self._db.commit()
        except (sqlite3.Error, aiosqlite.Error) as exc:
            msg = f"Failed to update SSRF violation status: {exc}"
            logger.exception(PERSISTENCE_SSRF_VIOLATION_SAVE_FAILED, error=msg)
            raise PersistenceError(msg) from exc

        return cursor.rowcount > 0


def _row_to_violation(row: Any) -> SsrfViolation:
    """Convert a SQLite row tuple to an SsrfViolation.

    Args:
        row: A tuple of column values matching _COLS order.

    Returns:
        An ``SsrfViolation`` instance.
    """
    (
        id_,
        timestamp,
        url,
        hostname,
        port,
        resolved_ip,
        blocked_range,
        provider_name,
        status,
        resolved_by,
        resolved_at,
    ) = row

    return SsrfViolation(
        id=id_,
        timestamp=datetime.fromisoformat(timestamp),
        url=url,
        hostname=hostname,
        port=port,
        resolved_ip=resolved_ip,
        blocked_range=blocked_range,
        provider_name=provider_name,
        status=SsrfViolationStatus(status),
        resolved_by=resolved_by,
        resolved_at=datetime.fromisoformat(resolved_at) if resolved_at else None,
    )
