"""SQLite repository implementation for approval items."""

import json
import sqlite3
from datetime import datetime

import aiosqlite  # noqa: TC002
from aiosqlite import Row  # noqa: TC002

from synthorg.core.approval import ApprovalItem
from synthorg.core.enums import ApprovalRiskLevel, ApprovalStatus
from synthorg.observability import get_logger
from synthorg.observability.events.api import (
    API_APPROVAL_REPO_DELETED,
    API_APPROVAL_REPO_FAILED,
    API_APPROVAL_REPO_FETCHED,
    API_APPROVAL_REPO_LISTED,
    API_APPROVAL_REPO_SAVED,
)
from synthorg.persistence.errors import ConstraintViolationError, QueryError

logger = get_logger(__name__)


def _row_to_item(row: Row) -> ApprovalItem:
    """Convert a database row to an ApprovalItem.

    Raises:
        QueryError: If the row contains corrupt or unparseable data.
    """
    try:
        metadata_raw: dict[str, str] = json.loads(str(row[13]))
        return ApprovalItem(
            id=str(row[0]),
            action_type=str(row[1]),
            title=str(row[2]),
            description=str(row[3]),
            requested_by=str(row[4]),
            risk_level=ApprovalRiskLevel(str(row[5])),
            status=ApprovalStatus(str(row[6])),
            created_at=datetime.fromisoformat(str(row[7])),
            expires_at=(
                datetime.fromisoformat(str(row[8])) if row[8] is not None else None
            ),
            decided_at=(
                datetime.fromisoformat(str(row[9])) if row[9] is not None else None
            ),
            decided_by=str(row[10]) if row[10] is not None else None,
            decision_reason=str(row[11]) if row[11] is not None else None,
            task_id=str(row[12]) if row[12] is not None else None,
            metadata=metadata_raw,
        )
    except (json.JSONDecodeError, ValueError, TypeError, KeyError) as exc:
        row_id = str(row[0]) if row else "<unknown>"
        msg = f"Failed to parse approval row {row_id!r}: {exc}"
        logger.exception(API_APPROVAL_REPO_FAILED, row_id=row_id, error=msg)
        raise QueryError(msg) from exc


class SQLiteApprovalRepository:
    """SQLite-backed approval item repository.

    Provides CRUD operations for approval items using a shared
    ``aiosqlite.Connection``.

    Args:
        db: An open aiosqlite connection.
    """

    def __init__(self, db: aiosqlite.Connection) -> None:
        self._db = db

    async def save(self, item: ApprovalItem) -> None:
        """Upsert an approval item.

        Args:
            item: The approval item to persist.

        Raises:
            ConstraintViolationError: On constraint violations.
            QueryError: On other database errors.
        """
        sql = """
            INSERT INTO approvals (
                id, action_type, title, description, requested_by,
                risk_level, status, created_at, expires_at,
                decided_at, decided_by, decision_reason,
                task_id, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                status = excluded.status,
                decided_at = excluded.decided_at,
                decided_by = excluded.decided_by,
                decision_reason = excluded.decision_reason,
                metadata = excluded.metadata
        """
        params = (
            item.id,
            item.action_type,
            item.title,
            item.description,
            item.requested_by,
            item.risk_level.value,
            item.status.value,
            item.created_at.isoformat(),
            item.expires_at.isoformat() if item.expires_at else None,
            item.decided_at.isoformat() if item.decided_at else None,
            item.decided_by,
            item.decision_reason,
            item.task_id,
            json.dumps(item.metadata),
        )
        try:
            await self._db.execute(sql, params)
            await self._db.commit()
        except sqlite3.IntegrityError as exc:
            await self._db.rollback()
            msg = f"Constraint violation saving approval {item.id!r}: {exc}"
            logger.exception(API_APPROVAL_REPO_FAILED, approval_id=item.id, error=msg)
            raise ConstraintViolationError(msg) from exc
        except Exception as exc:
            await self._db.rollback()
            msg = f"Failed to save approval {item.id!r}: {exc}"
            logger.exception(API_APPROVAL_REPO_FAILED, approval_id=item.id, error=msg)
            raise QueryError(msg) from exc
        logger.info(
            API_APPROVAL_REPO_SAVED,
            approval_id=item.id,
            status=item.status.value,
        )

    async def get(self, approval_id: str) -> ApprovalItem | None:
        """Get an approval item by ID.

        Args:
            approval_id: The approval identifier.

        Returns:
            The approval item, or None if not found.
        """
        sql = """
            SELECT id, action_type, title, description, requested_by,
                   risk_level, status, created_at, expires_at,
                   decided_at, decided_by, decision_reason,
                   task_id, metadata
            FROM approvals WHERE id = ?
        """
        try:
            cursor = await self._db.execute(sql, (approval_id,))
            row = await cursor.fetchone()
        except Exception as exc:
            msg = f"Failed to fetch approval {approval_id!r}: {exc}"
            logger.exception(
                API_APPROVAL_REPO_FAILED,
                approval_id=approval_id,
                error=msg,
            )
            raise QueryError(msg) from exc
        if row is None:
            return None
        item = _row_to_item(row)
        logger.debug(API_APPROVAL_REPO_FETCHED, approval_id=approval_id)
        return item

    async def list_items(
        self,
        *,
        status: ApprovalStatus | None = None,
        risk_level: ApprovalRiskLevel | None = None,
        action_type: str | None = None,
    ) -> tuple[ApprovalItem, ...]:
        """List approval items with optional filters.

        Args:
            status: Filter by approval status.
            risk_level: Filter by risk level.
            action_type: Filter by action type.

        Returns:
            Tuple of matching approval items.
        """
        clauses: list[str] = []
        params: list[str] = []
        if status is not None:
            clauses.append("status = ?")
            params.append(status.value)
        if risk_level is not None:
            clauses.append("risk_level = ?")
            params.append(risk_level.value)
        if action_type is not None:
            clauses.append("action_type = ?")
            params.append(action_type)
        where = " AND ".join(clauses) if clauses else "1=1"
        sql = f"""
            SELECT id, action_type, title, description, requested_by,
                   risk_level, status, created_at, expires_at,
                   decided_at, decided_by, decision_reason,
                   task_id, metadata
            FROM approvals WHERE {where}
            ORDER BY created_at DESC
        """  # noqa: S608
        try:
            cursor = await self._db.execute(sql, params)
            rows = await cursor.fetchall()
        except Exception as exc:
            msg = f"Failed to list approvals: {exc}"
            logger.exception(API_APPROVAL_REPO_FAILED, error=msg)
            raise QueryError(msg) from exc
        items = tuple(_row_to_item(r) for r in rows)
        logger.debug(API_APPROVAL_REPO_LISTED, count=len(items))
        return items

    async def delete(self, approval_id: str) -> bool:
        """Delete an approval item by ID.

        Args:
            approval_id: The approval identifier.

        Returns:
            True if the item was deleted, False if not found.
        """
        sql = "DELETE FROM approvals WHERE id = ?"
        try:
            cursor = await self._db.execute(sql, (approval_id,))
            await self._db.commit()
        except Exception as exc:
            await self._db.rollback()
            msg = f"Failed to delete approval {approval_id!r}: {exc}"
            logger.exception(
                API_APPROVAL_REPO_FAILED,
                approval_id=approval_id,
                error=msg,
            )
            raise QueryError(msg) from exc
        deleted = cursor.rowcount > 0
        logger.info(
            API_APPROVAL_REPO_DELETED,
            approval_id=approval_id,
            deleted=deleted,
        )
        return deleted
