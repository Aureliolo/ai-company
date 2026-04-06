"""SQLite repository implementation for risk tier overrides."""

import sqlite3
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import aiosqlite

from synthorg.core.enums import ApprovalRiskLevel
from synthorg.observability import get_logger
from synthorg.observability.events.persistence import (
    PERSISTENCE_RISK_OVERRIDE_QUERY_FAILED,
    PERSISTENCE_RISK_OVERRIDE_SAVE_FAILED,
    PERSISTENCE_RISK_OVERRIDE_SAVED,
)
from synthorg.persistence.errors import DuplicateRecordError, PersistenceError
from synthorg.security.rules.risk_override import RiskTierOverride

if TYPE_CHECKING:
    from synthorg.core.types import NotBlankStr

logger = get_logger(__name__)

_COLS = (
    "id, action_type, original_tier, override_tier, reason, "
    "created_by, created_at, expires_at, revoked_at, revoked_by"
)


class SQLiteRiskOverrideRepository:
    """SQLite implementation of the RiskOverrideRepository protocol.

    Args:
        db: An open aiosqlite connection.
    """

    def __init__(self, db: aiosqlite.Connection) -> None:
        self._db = db

    async def save(self, override: RiskTierOverride) -> None:
        """Persist a new risk tier override.

        Args:
            override: The override to save.

        Raises:
            DuplicateRecordError: If an override with the same ID exists.
            PersistenceError: If the save fails.
        """
        created_at_utc = override.created_at.astimezone(UTC).isoformat()
        expires_at_utc = override.expires_at.astimezone(UTC).isoformat()
        revoked_at_utc = (
            override.revoked_at.astimezone(UTC).isoformat()
            if override.revoked_at
            else None
        )

        try:
            await self._db.execute(
                f"INSERT INTO risk_overrides ({_COLS}) "  # noqa: S608
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    override.id,
                    override.action_type,
                    override.original_tier.value,
                    override.override_tier.value,
                    override.reason,
                    override.created_by,
                    created_at_utc,
                    expires_at_utc,
                    revoked_at_utc,
                    override.revoked_by,
                ),
            )
            await self._db.commit()
        except sqlite3.IntegrityError as exc:
            if "UNIQUE" in str(exc):
                msg = f"Risk override {override.id!r} already exists"
                raise DuplicateRecordError(msg) from exc
            msg = f"Failed to save risk override: {exc}"
            logger.exception(PERSISTENCE_RISK_OVERRIDE_SAVE_FAILED, error=msg)
            raise PersistenceError(msg) from exc
        except (sqlite3.Error, aiosqlite.Error) as exc:
            msg = f"Failed to save risk override: {exc}"
            logger.exception(PERSISTENCE_RISK_OVERRIDE_SAVE_FAILED, error=msg)
            raise PersistenceError(msg) from exc
        else:
            logger.debug(
                PERSISTENCE_RISK_OVERRIDE_SAVED,
                id=override.id,
            )

    async def get(self, override_id: NotBlankStr) -> RiskTierOverride | None:
        """Retrieve an override by ID.

        Args:
            override_id: The override identifier.

        Returns:
            The override, or None if not found.
        """
        try:
            cursor = await self._db.execute(
                f"SELECT {_COLS} FROM risk_overrides WHERE id = ?",  # noqa: S608
                (override_id,),
            )
            row = await cursor.fetchone()
        except (sqlite3.Error, aiosqlite.Error) as exc:
            msg = f"Failed to get risk override: {exc}"
            logger.exception(PERSISTENCE_RISK_OVERRIDE_QUERY_FAILED, error=msg)
            raise PersistenceError(msg) from exc

        if row is None:
            return None
        return _row_to_override(row)

    async def list_active(self) -> tuple[RiskTierOverride, ...]:
        """Return all active (non-expired, non-revoked) overrides.

        Returns:
            Tuple of active overrides, ordered by created_at DESC.
        """
        now_utc = datetime.now(tz=UTC).isoformat()
        try:
            cursor = await self._db.execute(
                f"SELECT {_COLS} FROM risk_overrides "  # noqa: S608
                "WHERE revoked_at IS NULL AND expires_at > ? "
                "ORDER BY created_at DESC",
                (now_utc,),
            )
            rows = await cursor.fetchall()
        except (sqlite3.Error, aiosqlite.Error) as exc:
            msg = f"Failed to list active overrides: {exc}"
            logger.exception(PERSISTENCE_RISK_OVERRIDE_QUERY_FAILED, error=msg)
            raise PersistenceError(msg) from exc

        return tuple(_row_to_override(row) for row in rows)

    async def revoke(
        self,
        override_id: NotBlankStr,
        *,
        revoked_by: NotBlankStr,
        revoked_at: datetime,
    ) -> bool:
        """Mark an override as revoked.

        Args:
            override_id: The override to revoke.
            revoked_by: User who revoked it.
            revoked_at: When it was revoked.

        Returns:
            True if the override was found and revoked.
        """
        revoked_at_utc = revoked_at.astimezone(UTC).isoformat()
        try:
            cursor = await self._db.execute(
                "UPDATE risk_overrides SET revoked_at = ?, revoked_by = ? "
                "WHERE id = ? AND revoked_at IS NULL",
                (revoked_at_utc, revoked_by, override_id),
            )
            await self._db.commit()
        except (sqlite3.Error, aiosqlite.Error) as exc:
            msg = f"Failed to revoke risk override: {exc}"
            logger.exception(PERSISTENCE_RISK_OVERRIDE_SAVE_FAILED, error=msg)
            raise PersistenceError(msg) from exc

        return cursor.rowcount > 0


def _row_to_override(row: Any) -> RiskTierOverride:
    """Convert a SQLite row tuple to a RiskTierOverride.

    Args:
        row: A tuple of column values matching _COLS order.

    Returns:
        A ``RiskTierOverride`` instance.
    """
    (
        id_,
        action_type,
        original_tier,
        override_tier,
        reason,
        created_by,
        created_at,
        expires_at,
        revoked_at,
        revoked_by,
    ) = row

    return RiskTierOverride(
        id=id_,
        action_type=action_type,
        original_tier=ApprovalRiskLevel(original_tier),
        override_tier=ApprovalRiskLevel(override_tier),
        reason=reason,
        created_by=created_by,
        created_at=datetime.fromisoformat(created_at),
        expires_at=datetime.fromisoformat(expires_at),
        revoked_at=datetime.fromisoformat(revoked_at) if revoked_at else None,
        revoked_by=revoked_by,
    )
