"""SQLite repository for the human escalation queue (#1418).

Mirrors the shape of :class:`SQLiteApprovalRepository`: a shared
``aiosqlite.Connection``, row-mapping helper, and async CRUD with
structured logging.  Stores the :class:`Conflict` snapshot and the
optional decision payload as JSON TEXT columns for schema simplicity.
"""

import json
import sqlite3
from datetime import datetime

import aiosqlite
from aiosqlite import Row
from pydantic import TypeAdapter

from synthorg.communication.conflict_resolution.escalation.models import (
    Escalation,
    EscalationDecision,
    EscalationStatus,
)
from synthorg.communication.conflict_resolution.escalation.protocol import (
    EscalationQueueStore,
)
from synthorg.communication.conflict_resolution.models import Conflict
from synthorg.observability import get_logger
from synthorg.observability.events.api import API_REQUEST_ERROR
from synthorg.persistence.errors import ConstraintViolationError, QueryError

logger = get_logger(__name__)

_DEFAULT_LIMIT = 50
_DEFAULT_OFFSET = 0

_decision_adapter: TypeAdapter[EscalationDecision] = TypeAdapter(EscalationDecision)

_UPSERT_SQL = """
    INSERT INTO conflict_escalations (
        id, conflict_id, conflict_json, status,
        created_at, expires_at, decided_at, decided_by, decision_json
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
"""

_SELECT_COLS = (
    "id, conflict_id, conflict_json, status, "
    "created_at, expires_at, decided_at, decided_by, decision_json"
)


def _row_to_escalation(row: Row) -> Escalation:
    """Deserialise a DB row into an :class:`Escalation`."""
    try:
        conflict = Conflict.model_validate_json(str(row["conflict_json"]))
        decision: EscalationDecision | None = None
        decision_raw = row["decision_json"]
        if decision_raw is not None:
            decision = _decision_adapter.validate_json(str(decision_raw))
        return Escalation(
            id=str(row["id"]),
            conflict=conflict,
            status=EscalationStatus(str(row["status"])),
            created_at=datetime.fromisoformat(str(row["created_at"])),
            expires_at=(
                datetime.fromisoformat(str(row["expires_at"]))
                if row["expires_at"] is not None
                else None
            ),
            decided_at=(
                datetime.fromisoformat(str(row["decided_at"]))
                if row["decided_at"] is not None
                else None
            ),
            decided_by=(
                str(row["decided_by"]) if row["decided_by"] is not None else None
            ),
            decision=decision,
        )
    except (json.JSONDecodeError, ValueError, TypeError, KeyError) as exc:
        try:
            row_id = str(row["id"]) if row else "<unknown>"
        except TypeError, KeyError:
            row_id = "<unknown>"
        msg = f"Failed to parse escalation row {row_id!r}: {exc}"
        logger.exception(API_REQUEST_ERROR, row_id=row_id, error=msg)
        raise QueryError(msg) from exc


class SQLiteEscalationRepository(EscalationQueueStore):
    """aiosqlite-backed :class:`EscalationQueueStore`.

    Args:
        db: An open aiosqlite connection (typically the one shared by
            the :class:`SQLiteBackend` with all other SQLite repos).
    """

    def __init__(self, db: aiosqlite.Connection) -> None:
        """Initialise the repository with a shared aiosqlite connection."""
        self._db: aiosqlite.Connection = db
        self._db.row_factory = aiosqlite.Row

    async def create(self, escalation: Escalation) -> None:
        """Insert a PENDING escalation row."""
        if escalation.status != EscalationStatus.PENDING:
            msg = "create() requires status=PENDING"
            raise ValueError(msg)
        params = (
            escalation.id,
            escalation.conflict.id,
            escalation.conflict.model_dump_json(),
            escalation.status.value,
            escalation.created_at.isoformat(),
            escalation.expires_at.isoformat() if escalation.expires_at else None,
            None,
            None,
            None,
        )
        try:
            await self._db.execute(_UPSERT_SQL, params)
            await self._db.commit()
        except sqlite3.IntegrityError as exc:
            await self._db.rollback()
            msg = f"Escalation {escalation.id!r} already exists"
            raise ConstraintViolationError(msg, constraint=str(exc)) from exc
        except (sqlite3.Error, aiosqlite.Error) as exc:
            await self._db.rollback()
            msg = f"Failed to create escalation {escalation.id!r}: {exc}"
            raise QueryError(msg) from exc

    async def get(self, escalation_id: str) -> Escalation | None:
        """Fetch by ID."""
        sql = f"SELECT {_SELECT_COLS} FROM conflict_escalations WHERE id = ?"  # noqa: S608
        try:
            cursor = await self._db.execute(sql, (escalation_id,))
            row = await cursor.fetchone()
        except (sqlite3.Error, aiosqlite.Error) as exc:
            msg = f"Failed to fetch escalation {escalation_id!r}: {exc}"
            raise QueryError(msg) from exc
        if row is None:
            return None
        return _row_to_escalation(row)

    async def list_items(
        self,
        *,
        status: EscalationStatus | None = EscalationStatus.PENDING,
        limit: int = _DEFAULT_LIMIT,
        offset: int = _DEFAULT_OFFSET,
    ) -> tuple[tuple[Escalation, ...], int]:
        """Page over rows filtered by status."""
        if limit <= 0:
            msg = "limit must be positive"
            raise ValueError(msg)
        if offset < 0:
            msg = "offset must be non-negative"
            raise ValueError(msg)
        where = "1=1"
        params: list[object] = []
        if status is not None:
            where = "status = ?"
            params.append(status.value)
        count_sql = f"SELECT COUNT(*) AS total FROM conflict_escalations WHERE {where}"  # noqa: S608
        page_sql = (
            f"SELECT {_SELECT_COLS} FROM conflict_escalations "  # noqa: S608
            f"WHERE {where} ORDER BY created_at ASC LIMIT ? OFFSET ?"
        )
        try:
            count_cursor = await self._db.execute(count_sql, params)
            count_row = await count_cursor.fetchone()
            total = int(count_row["total"]) if count_row is not None else 0
            page_cursor = await self._db.execute(page_sql, (*params, limit, offset))
            rows = await page_cursor.fetchall()
        except (sqlite3.Error, aiosqlite.Error) as exc:
            msg = f"Failed to list escalations: {exc}"
            raise QueryError(msg) from exc
        page = tuple(_row_to_escalation(r) for r in rows)
        return page, total

    async def apply_decision(
        self,
        escalation_id: str,
        *,
        decision: EscalationDecision,
        decided_by: str,
    ) -> Escalation:
        """Transition PENDING -> DECIDED atomically."""
        now_iso = datetime.now().astimezone().isoformat()
        decision_json = _decision_adapter.dump_json(decision).decode("utf-8")
        return await self._update_terminal(
            escalation_id,
            new_status=EscalationStatus.DECIDED,
            decided_at_iso=now_iso,
            decided_by=decided_by,
            decision_json=decision_json,
            allowed_from={EscalationStatus.PENDING},
        )

    async def cancel(self, escalation_id: str, *, cancelled_by: str) -> Escalation:
        """Transition PENDING -> CANCELLED."""
        now_iso = datetime.now().astimezone().isoformat()
        return await self._update_terminal(
            escalation_id,
            new_status=EscalationStatus.CANCELLED,
            decided_at_iso=now_iso,
            decided_by=cancelled_by,
            decision_json=None,
            allowed_from={EscalationStatus.PENDING},
        )

    async def mark_expired(self, now_iso: str) -> tuple[str, ...]:
        """Expire PENDING rows past their deadline."""
        select_sql = (
            "SELECT id FROM conflict_escalations "
            "WHERE status = 'pending' AND expires_at IS NOT NULL "
            "AND expires_at <= ?"
        )
        try:
            cursor = await self._db.execute(select_sql, (now_iso,))
            rows = await cursor.fetchall()
        except (sqlite3.Error, aiosqlite.Error) as exc:
            msg = f"Failed to query expiring escalations: {exc}"
            raise QueryError(msg) from exc
        ids = tuple(str(r["id"]) for r in rows)
        if not ids:
            return ()
        placeholders = ",".join("?" * len(ids))
        # Placeholders are always generated from the `ids` list we just
        # fetched -- no user input -- so the f-string is safe.
        update_sql = (
            "UPDATE conflict_escalations SET status='expired', decided_at=? "  # noqa: S608
            f"WHERE id IN ({placeholders}) AND status='pending'"
        )
        try:
            await self._db.execute(update_sql, (now_iso, *ids))
            await self._db.commit()
        except (sqlite3.Error, aiosqlite.Error) as exc:
            await self._db.rollback()
            msg = f"Failed to mark escalations expired: {exc}"
            raise QueryError(msg) from exc
        return ids

    async def close(self) -> None:
        """No-op: the connection is owned by the persistence backend."""
        return

    async def _update_terminal(  # noqa: PLR0913
        self,
        escalation_id: str,
        *,
        new_status: EscalationStatus,
        decided_at_iso: str,
        decided_by: str,
        decision_json: str | None,
        allowed_from: set[EscalationStatus],
    ) -> Escalation:
        """Apply a terminal state transition under a conditional WHERE.

        ``allowed_from`` is an internal EscalationStatus enum set -- the
        ``IN (...)`` clause interpolates values from a trusted enum, not
        caller input, so the S608 is a false positive.
        """
        allowed = ",".join(f"'{s.value}'" for s in allowed_from)
        update_sql = (
            "UPDATE conflict_escalations SET "  # noqa: S608
            "status = ?, decided_at = ?, decided_by = ?, decision_json = ? "
            f"WHERE id = ? AND status IN ({allowed})"
        )
        params = (
            new_status.value,
            decided_at_iso,
            decided_by,
            decision_json,
            escalation_id,
        )
        try:
            cursor = await self._db.execute(update_sql, params)
            await self._db.commit()
        except (sqlite3.Error, aiosqlite.Error) as exc:
            await self._db.rollback()
            msg = f"Failed to update escalation {escalation_id!r}: {exc}"
            raise QueryError(msg) from exc
        if cursor.rowcount == 0:
            existing = await self.get(escalation_id)
            if existing is None:
                msg = f"Escalation {escalation_id!r} not found"
                raise KeyError(msg)
            msg = (
                f"Escalation {escalation_id!r} is {existing.status.value}, "
                f"cannot transition to {new_status.value}"
            )
            raise ValueError(msg)
        updated = await self.get(escalation_id)
        if updated is None:
            msg = f"Escalation {escalation_id!r} vanished after update"
            raise QueryError(msg)
        return updated
