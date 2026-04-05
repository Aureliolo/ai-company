"""SQLite repository implementation for decision records.

Append-only: records can be appended and queried but never updated or
deleted, preserving audit integrity.  Version numbers for
``(task_id, version)`` are computed atomically in SQL via a subquery
to eliminate the TOCTOU race that a read-then-write pattern would
create under concurrent review gate decisions.
"""

import json
import sqlite3
from datetime import UTC
from typing import TYPE_CHECKING, Final

import aiosqlite
from pydantic import AwareDatetime, ValidationError

from synthorg.core.enums import DecisionOutcome  # noqa: TC001
from synthorg.engine.decisions import DecisionRecord
from synthorg.observability import get_logger
from synthorg.observability.events.persistence import (
    PERSISTENCE_DECISION_RECORD_DESERIALIZE_FAILED,
    PERSISTENCE_DECISION_RECORD_QUERIED,
    PERSISTENCE_DECISION_RECORD_QUERY_FAILED,
    PERSISTENCE_DECISION_RECORD_SAVE_FAILED,
    PERSISTENCE_DECISION_RECORD_SAVED,
)
from synthorg.persistence.errors import DuplicateRecordError, QueryError
from synthorg.persistence.repositories import DecisionRole  # noqa: TC001

if TYPE_CHECKING:
    from synthorg.core.types import NotBlankStr

logger = get_logger(__name__)

_COLS = (
    "id, task_id, approval_id, executing_agent_id, reviewer_agent_id, "
    "decision, reason, criteria_snapshot, recorded_at, version, metadata"
)

# Maps ``DecisionRole`` Literal values to their corresponding column
# name.  Keeps the dynamic-column SQL in ``list_by_agent`` bounded to a
# closed set of identifiers that are never user-supplied.
_ROLE_TO_COLUMN: Final[dict[str, str]] = {
    "executor": "executing_agent_id",
    "reviewer": "reviewer_agent_id",
}

_INSERT_SQL: Final[str] = """\
INSERT INTO decision_records (
    id, task_id, approval_id, executing_agent_id, reviewer_agent_id,
    decision, reason, criteria_snapshot, recorded_at, version, metadata
) VALUES (
    :id, :task_id, :approval_id, :executing_agent_id, :reviewer_agent_id,
    :decision, :reason, :criteria_snapshot, :recorded_at,
    (SELECT COALESCE(MAX(version), 0) + 1
       FROM decision_records WHERE task_id = :task_id),
    :metadata
)"""


def _build_insert_params(  # noqa: PLR0913
    *,
    record_id: NotBlankStr,
    task_id: NotBlankStr,
    approval_id: NotBlankStr | None,
    executing_agent_id: NotBlankStr,
    reviewer_agent_id: NotBlankStr,
    decision: DecisionOutcome,
    reason: str | None,
    criteria_snapshot: tuple[NotBlankStr, ...],
    recorded_at: AwareDatetime,
    metadata: dict[str, object],
) -> dict[str, object]:
    """Shape the bound-parameter dict for the INSERT statement.

    Normalizes ``recorded_at`` to UTC (ISO 8601 with ``+00:00`` offset)
    so lexicographic ordering of the ``recorded_at`` column is
    equivalent to chronological ordering across mixed-timezone callers.
    """
    return {
        "id": record_id,
        "task_id": task_id,
        "approval_id": approval_id,
        "executing_agent_id": executing_agent_id,
        "reviewer_agent_id": reviewer_agent_id,
        "decision": decision.value,
        "reason": reason,
        "criteria_snapshot": json.dumps(list(criteria_snapshot)),
        "recorded_at": recorded_at.astimezone(UTC).isoformat(),
        "metadata": json.dumps(metadata),
    }


def _is_unique_constraint_error(exc: sqlite3.IntegrityError) -> bool:
    """Return True when the exception is a UNIQUE/PRIMARY KEY violation.

    Uses ``sqlite_errorname`` (Python 3.11+) as the authoritative signal
    rather than brittle substring matching on the error message.  The
    project targets Python 3.14+, so the attribute is always present.
    """
    return exc.sqlite_errorname in {
        "SQLITE_CONSTRAINT_UNIQUE",
        "SQLITE_CONSTRAINT_PRIMARYKEY",
    }


class SQLiteDecisionRepository:
    """SQLite implementation of the ``DecisionRepository`` protocol.

    Append-only: decision records are immutable audit entries of
    review gate decisions.  Timestamps are normalized to UTC before
    storage for consistent lexicographic ordering.

    Args:
        db: An open aiosqlite connection.
    """

    def __init__(self, db: aiosqlite.Connection) -> None:
        self._db = db

    async def append_with_next_version(  # noqa: PLR0913
        self,
        *,
        record_id: NotBlankStr,
        task_id: NotBlankStr,
        approval_id: NotBlankStr | None,
        executing_agent_id: NotBlankStr,
        reviewer_agent_id: NotBlankStr,
        decision: DecisionOutcome,
        reason: str | None,
        criteria_snapshot: tuple[NotBlankStr, ...],
        recorded_at: AwareDatetime,
        metadata: dict[str, object] | None = None,
    ) -> DecisionRecord:
        """Atomically insert a decision record with server-computed version.

        Version is derived via ``COALESCE(MAX(version), 0) + 1`` inside
        the ``INSERT`` statement itself.  That single statement is
        atomic under aiosqlite's per-statement serialization, and the
        ``UNIQUE(task_id, version)`` constraint rejects any race that
        somehow produces a duplicate -- surfaced as
        ``DuplicateRecordError``.  This matches the connection-level
        implicit transaction semantics used by every other SQLite repo
        in this backend (no explicit ``BEGIN``).

        See the ``DecisionRepository`` protocol for the full argument
        descriptions.  ``recorded_at`` is normalized to UTC before
        storage; records read back via ``get`` / ``list_by_task`` /
        ``list_by_agent`` will therefore always have UTC timestamps.
        ``metadata`` defaults to ``{}`` so callers that do not attach
        metadata do not have to pass an empty dict.

        Raises:
            DuplicateRecordError: If a record with ``record_id`` exists
                OR a concurrent write won the ``UNIQUE(task_id, version)``
                race.
            QueryError: If the operation fails.
        """
        params = _build_insert_params(
            record_id=record_id,
            task_id=task_id,
            approval_id=approval_id,
            executing_agent_id=executing_agent_id,
            reviewer_agent_id=reviewer_agent_id,
            decision=decision,
            reason=reason,
            criteria_snapshot=criteria_snapshot,
            recorded_at=recorded_at,
            metadata=metadata or {},
        )
        assigned_version = await self._execute_insert(record_id, params)
        record = DecisionRecord(
            id=record_id,
            task_id=task_id,
            approval_id=approval_id,
            executing_agent_id=executing_agent_id,
            reviewer_agent_id=reviewer_agent_id,
            decision=decision,
            reason=reason,
            criteria_snapshot=criteria_snapshot,
            recorded_at=recorded_at,
            version=assigned_version,
            metadata=metadata or {},
        )
        logger.debug(
            PERSISTENCE_DECISION_RECORD_SAVED,
            record_id=record_id,
            task_id=task_id,
            version=assigned_version,
        )
        return record

    async def _execute_insert(
        self,
        record_id: NotBlankStr,
        params: dict[str, object],
    ) -> int:
        """Insert the record and return the server-assigned version.

        Keeps ``append_with_next_version`` under the 50-line budget and
        centralizes the error-mapping / rollback logic for the write
        path.
        """
        try:
            await self._db.execute(_INSERT_SQL, params)
            cursor = await self._db.execute(
                "SELECT version FROM decision_records WHERE id = :id",
                {"id": record_id},
            )
            row = await cursor.fetchone()
            await self._db.commit()
        except sqlite3.IntegrityError as exc:
            await self._rollback_quietly()
            if _is_unique_constraint_error(exc):
                msg = f"Duplicate decision record {record_id!r}"
                logger.warning(
                    PERSISTENCE_DECISION_RECORD_SAVE_FAILED,
                    record_id=record_id,
                    error=str(exc),
                    sqlite_errorname=exc.sqlite_errorname,
                )
                raise DuplicateRecordError(msg) from exc
            msg = f"Failed to save decision record {record_id!r}"
            logger.exception(
                PERSISTENCE_DECISION_RECORD_SAVE_FAILED,
                record_id=record_id,
                error=str(exc),
                sqlite_errorname=exc.sqlite_errorname,
            )
            raise QueryError(msg) from exc
        except (sqlite3.Error, aiosqlite.Error) as exc:
            await self._rollback_quietly()
            msg = f"Failed to save decision record {record_id!r}"
            logger.exception(
                PERSISTENCE_DECISION_RECORD_SAVE_FAILED,
                record_id=record_id,
                error=str(exc),
            )
            raise QueryError(msg) from exc
        if row is None:
            # Defensive: fetchone can return None under aiosqlite's
            # type signature even though a successful INSERT + SELECT
            # of the same id should always find the row.  Surface the
            # anomaly loudly rather than silently swallowing it.
            msg = (
                f"Failed to read back decision record {record_id!r} "
                "immediately after insert"
            )
            task_id_value = params.get("task_id")
            logger.error(
                PERSISTENCE_DECISION_RECORD_SAVE_FAILED,
                record_id=record_id,
                task_id=task_id_value,
                error=msg,
            )
            raise QueryError(msg)
        return int(row["version"])

    async def _rollback_quietly(self) -> None:
        """Roll back the current transaction, swallowing rollback errors.

        If the rollback itself fails (e.g. connection dropped), we log
        the secondary failure but do not shadow the caller's original
        exception -- that's the one the caller needs to see.
        """
        try:
            await self._db.rollback()
        except (sqlite3.Error, aiosqlite.Error) as rollback_exc:
            logger.warning(
                PERSISTENCE_DECISION_RECORD_SAVE_FAILED,
                stage="rollback",
                error=str(rollback_exc),
            )

    async def get(self, record_id: NotBlankStr) -> DecisionRecord | None:
        """Retrieve a decision record by ID."""
        try:
            cursor = await self._db.execute(
                f"SELECT {_COLS} FROM decision_records WHERE id = ?",  # noqa: S608
                (record_id,),
            )
            row = await cursor.fetchone()
        except (sqlite3.Error, aiosqlite.Error) as exc:
            msg = f"Failed to fetch decision record {record_id!r}"
            logger.exception(
                PERSISTENCE_DECISION_RECORD_QUERY_FAILED,
                record_id=record_id,
                error=str(exc),
            )
            raise QueryError(msg) from exc
        if row is None:
            return None
        return self._row_to_record(dict(row))

    async def list_by_task(self, task_id: NotBlankStr) -> tuple[DecisionRecord, ...]:
        """List decision records for a task, ordered by version ascending."""
        try:
            cursor = await self._db.execute(
                f"SELECT {_COLS} FROM decision_records "  # noqa: S608
                "WHERE task_id = ? ORDER BY version ASC",
                (task_id,),
            )
            rows = await cursor.fetchall()
        except (sqlite3.Error, aiosqlite.Error) as exc:
            msg = f"Failed to list decision records for task {task_id!r}"
            logger.exception(
                PERSISTENCE_DECISION_RECORD_QUERY_FAILED,
                task_id=task_id,
                error=str(exc),
            )
            raise QueryError(msg) from exc
        results = tuple(self._row_to_record(dict(row)) for row in rows)
        logger.debug(
            PERSISTENCE_DECISION_RECORD_QUERIED,
            task_id=task_id,
            count=len(results),
        )
        return results

    async def list_by_agent(
        self,
        agent_id: NotBlankStr,
        *,
        role: DecisionRole,
    ) -> tuple[DecisionRecord, ...]:
        """List decision records where the agent acted in the given role.

        ``role`` is validated via ``Literal`` at the type level, but we
        re-check at runtime to guard against bad callers that bypass
        type checking.  A rejected role is logged before raising.
        """
        # Runtime defense in depth: the Literal prevents type-safe
        # callers from passing bad values, but the ``_ROLE_TO_COLUMN``
        # lookup re-validates for untyped call sites.  Using a dict
        # lookup instead of if/elif keeps the column name derivation
        # closed over a bounded set of hard-coded identifiers, which
        # is what justifies the S608 noqa on the f-string SQL below.
        role_str: str = role
        try:
            column = _ROLE_TO_COLUMN[role_str]
        except KeyError as exc:
            msg = f"role must be 'executor' or 'reviewer', got {role_str!r}"
            logger.warning(
                PERSISTENCE_DECISION_RECORD_QUERY_FAILED,
                agent_id=agent_id,
                role=role_str,
                error=msg,
            )
            raise ValueError(msg) from exc
        try:
            # column is a closed-set value from _ROLE_TO_COLUMN, never
            # user-supplied; agent_id flows through the positional
            # placeholder.
            query = (
                f"SELECT {_COLS} FROM decision_records "  # noqa: S608
                f"WHERE {column} = ? ORDER BY recorded_at DESC"
            )
            cursor = await self._db.execute(query, (agent_id,))
            rows = await cursor.fetchall()
        except (sqlite3.Error, aiosqlite.Error) as exc:
            msg = (
                f"Failed to list decision records for agent {agent_id!r} (role={role})"
            )
            logger.exception(
                PERSISTENCE_DECISION_RECORD_QUERY_FAILED,
                agent_id=agent_id,
                role=role,
                error=str(exc),
            )
            raise QueryError(msg) from exc
        results = tuple(self._row_to_record(dict(row)) for row in rows)
        logger.debug(
            PERSISTENCE_DECISION_RECORD_QUERIED,
            agent_id=agent_id,
            role=role,
            count=len(results),
        )
        return results

    def _row_to_record(self, row: dict[str, object]) -> DecisionRecord:
        """Convert a database row to a ``DecisionRecord`` model.

        ``KeyError`` is deliberately NOT caught -- a missing required
        column indicates schema drift, a programming error that must
        surface loudly.  Direct ``row["col"]`` access (rather than
        ``.get()``) on ``NOT NULL`` columns preserves this behavior.
        """
        try:
            parsed: dict[str, object] = dict(row)
            raw_criteria = row["criteria_snapshot"]
            raw_metadata = row["metadata"]
            if isinstance(raw_criteria, str):
                parsed["criteria_snapshot"] = tuple(json.loads(raw_criteria))
            if isinstance(raw_metadata, str):
                parsed["metadata"] = json.loads(raw_metadata)
            return DecisionRecord.model_validate(parsed)
        except (ValidationError, json.JSONDecodeError, TypeError) as exc:
            msg = (
                f"Failed to deserialize decision record {row.get('id')!r}: "
                f"{type(exc).__name__}"
            )
            logger.exception(
                PERSISTENCE_DECISION_RECORD_DESERIALIZE_FAILED,
                record_id=row.get("id"),
                error=str(exc),
                error_type=type(exc).__name__,
            )
            raise QueryError(msg) from exc
