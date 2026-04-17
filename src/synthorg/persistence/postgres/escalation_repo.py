"""Postgres repository for the human escalation queue (#1418).

Sibling of :class:`SQLiteEscalationRepository` backed by
``psycopg_pool.AsyncConnectionPool``.  Uses native ``JSONB`` for the
conflict snapshot and the decision payload, and ``TIMESTAMPTZ`` for
all timestamps -- mirrors the Postgres sibling pattern from
``parked_context_repo.py``.
"""

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
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

if TYPE_CHECKING:
    from psycopg_pool import AsyncConnectionPool

logger = get_logger(__name__)

_DEFAULT_LIMIT = 50
_DEFAULT_OFFSET = 0

_decision_adapter: TypeAdapter[EscalationDecision] = TypeAdapter(EscalationDecision)

_SELECT_COLS = (
    "id, conflict_id, conflict_json, status, "
    "created_at, expires_at, decided_at, decided_by, decision_json"
)


def _row_to_escalation(row: dict) -> Escalation:
    """Deserialise a Postgres row dict into an :class:`Escalation`.

    ``conflict_json`` and ``decision_json`` arrive as native Python
    objects (psycopg decodes ``JSONB`` automatically); the helper
    re-serialises them so Pydantic's ``model_validate_json`` path is
    exercised uniformly across backends.
    """
    try:
        conflict = Conflict.model_validate(row["conflict_json"])
        decision: EscalationDecision | None = None
        if row["decision_json"] is not None:
            decision = _decision_adapter.validate_python(row["decision_json"])
        return Escalation(
            id=str(row["id"]),
            conflict=conflict,
            status=EscalationStatus(str(row["status"])),
            created_at=row["created_at"],
            expires_at=row["expires_at"],
            decided_at=row["decided_at"],
            decided_by=(
                str(row["decided_by"]) if row["decided_by"] is not None else None
            ),
            decision=decision,
        )
    except (json.JSONDecodeError, ValueError, TypeError, KeyError) as exc:
        row_id = str(row.get("id", "<unknown>"))
        msg = f"Failed to parse escalation row {row_id!r}: {exc}"
        logger.exception(API_REQUEST_ERROR, row_id=row_id, error=msg)
        raise QueryError(msg) from exc


class PostgresEscalationRepository(EscalationQueueStore):
    """``psycopg``-backed :class:`EscalationQueueStore`.

    Args:
        pool: Open ``psycopg_pool.AsyncConnectionPool`` owned by the
            :class:`PostgresPersistenceBackend`.
    """

    def __init__(self, pool: AsyncConnectionPool) -> None:
        """Initialise the repository with a shared connection pool."""
        self._pool = pool

    async def create(self, escalation: Escalation) -> None:
        """Insert a PENDING escalation row."""
        if escalation.status != EscalationStatus.PENDING:
            msg = "create() requires status=PENDING"
            raise ValueError(msg)
        conflict_payload = Jsonb(escalation.conflict.model_dump(mode="json"))
        params = {
            "id": escalation.id,
            "conflict_id": escalation.conflict.id,
            "conflict_json": conflict_payload,
            "status": escalation.status.value,
            "created_at": escalation.created_at,
            "expires_at": escalation.expires_at,
            "decided_at": None,
            "decided_by": None,
            "decision_json": None,
        }
        try:
            async with self._pool.connection() as conn, conn.cursor() as cur:
                await cur.execute(
                    """\
INSERT INTO conflict_escalations (
    id, conflict_id, conflict_json, status,
    created_at, expires_at, decided_at, decided_by, decision_json
) VALUES (
    %(id)s, %(conflict_id)s, %(conflict_json)s, %(status)s,
    %(created_at)s, %(expires_at)s, %(decided_at)s, %(decided_by)s, %(decision_json)s
)""",
                    params,
                )
                await conn.commit()
        except psycopg.errors.UniqueViolation as exc:
            msg = f"Escalation {escalation.id!r} already exists"
            raise ConstraintViolationError(msg, constraint=str(exc)) from exc
        except psycopg.Error as exc:
            msg = f"Failed to create escalation {escalation.id!r}: {exc}"
            raise QueryError(msg) from exc

    async def get(self, escalation_id: str) -> Escalation | None:
        """Fetch by ID."""
        try:
            async with (
                self._pool.connection() as conn,
                conn.cursor(row_factory=dict_row) as cur,
            ):
                await cur.execute(
                    f"SELECT {_SELECT_COLS} FROM conflict_escalations "  # noqa: S608
                    "WHERE id = %s",
                    (escalation_id,),
                )
                row = await cur.fetchone()
        except psycopg.Error as exc:
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
        if status is not None:
            where_sql = "WHERE status = %s"
            where_params: tuple[object, ...] = (status.value,)
        else:
            where_sql = ""
            where_params = ()
        try:
            async with (
                self._pool.connection() as conn,
                conn.cursor(row_factory=dict_row) as cur,
            ):
                await cur.execute(
                    f"SELECT COUNT(*) AS total FROM conflict_escalations {where_sql}",  # noqa: S608
                    where_params,
                )
                count_row = await cur.fetchone()
                total = int(count_row["total"]) if count_row is not None else 0
                await cur.execute(
                    f"SELECT {_SELECT_COLS} FROM conflict_escalations "  # noqa: S608
                    f"{where_sql} ORDER BY created_at ASC "
                    "LIMIT %s OFFSET %s",
                    (*where_params, limit, offset),
                )
                rows = await cur.fetchall()
        except psycopg.Error as exc:
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
        return await self._update_terminal(
            escalation_id,
            new_status=EscalationStatus.DECIDED,
            decided_by=decided_by,
            decision=decision,
        )

    async def cancel(self, escalation_id: str, *, cancelled_by: str) -> Escalation:
        """Transition PENDING -> CANCELLED."""
        return await self._update_terminal(
            escalation_id,
            new_status=EscalationStatus.CANCELLED,
            decided_by=cancelled_by,
            decision=None,
        )

    async def mark_expired(self, now_iso: str) -> tuple[str, ...]:
        """Expire PENDING rows past their deadline."""
        now_dt = datetime.fromisoformat(now_iso)
        try:
            async with (
                self._pool.connection() as conn,
                conn.cursor() as cur,
            ):
                await cur.execute(
                    "UPDATE conflict_escalations SET "
                    "status = 'expired', decided_at = %s "
                    "WHERE status = 'pending' "
                    "AND expires_at IS NOT NULL AND expires_at <= %s "
                    "RETURNING id",
                    (now_dt, now_dt),
                )
                rows = await cur.fetchall()
                await conn.commit()
        except psycopg.Error as exc:
            msg = f"Failed to mark escalations expired: {exc}"
            raise QueryError(msg) from exc
        return tuple(str(r[0]) for r in rows)

    async def close(self) -> None:
        """No-op: the pool is owned by the persistence backend."""
        return

    async def _update_terminal(
        self,
        escalation_id: str,
        *,
        new_status: EscalationStatus,
        decided_by: str,
        decision: EscalationDecision | None,
    ) -> Escalation:
        """Apply a terminal state transition gated on current status."""
        decided_at = datetime.now(UTC)
        decision_payload: Jsonb | None = None
        if decision is not None:
            decision_payload = Jsonb(
                json.loads(_decision_adapter.dump_json(decision).decode("utf-8")),
            )
        try:
            async with (
                self._pool.connection() as conn,
                conn.cursor(row_factory=dict_row) as cur,
            ):
                await cur.execute(
                    "UPDATE conflict_escalations SET "  # noqa: S608
                    "status = %s, decided_at = %s, decided_by = %s, "
                    "decision_json = %s "
                    "WHERE id = %s AND status = 'pending' "
                    f"RETURNING {_SELECT_COLS}",
                    (
                        new_status.value,
                        decided_at,
                        decided_by,
                        decision_payload,
                        escalation_id,
                    ),
                )
                updated_row = await cur.fetchone()
                await conn.commit()
                if updated_row is None:
                    await cur.execute(
                        "SELECT status FROM conflict_escalations WHERE id = %s",
                        (escalation_id,),
                    )
                    existing = await cur.fetchone()
                    if existing is None:
                        msg = f"Escalation {escalation_id!r} not found"
                        raise KeyError(msg)
                    msg = (
                        f"Escalation {escalation_id!r} is "
                        f"{existing['status']}, cannot transition to "
                        f"{new_status.value}"
                    )
                    raise ValueError(msg)
        except psycopg.Error as exc:
            msg = f"Failed to update escalation {escalation_id!r}: {exc}"
            raise QueryError(msg) from exc
        return _row_to_escalation(updated_row)
