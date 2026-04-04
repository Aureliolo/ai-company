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
from typing import TYPE_CHECKING

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


def _is_unique_constraint_error(exc: sqlite3.IntegrityError) -> bool:
    """Return True when the exception is a UNIQUE/PRIMARY KEY violation.

    Uses ``sqlite_errorname`` (Python 3.11+) as the authoritative signal
    rather than brittle substring matching on the error message.
    """
    name = getattr(exc, "sqlite_errorname", None)
    return name in {"SQLITE_CONSTRAINT_UNIQUE", "SQLITE_CONSTRAINT_PRIMARYKEY"}


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
        metadata: dict[str, object],
    ) -> DecisionRecord:
        """Atomically insert a decision record with server-computed version.

        Version is derived via
        ``COALESCE(MAX(version), 0) + 1`` inside a single ``BEGIN
        IMMEDIATE`` transaction so two concurrent writers cannot collide
        on the ``UNIQUE(task_id, version)`` constraint.

        Raises:
            DuplicateRecordError: If a record with ``record_id`` exists.
            QueryError: If the operation fails.
        """
        recorded_at_utc = recorded_at.astimezone(UTC).isoformat()
        params = {
            "id": record_id,
            "task_id": task_id,
            "approval_id": approval_id,
            "executing_agent_id": executing_agent_id,
            "reviewer_agent_id": reviewer_agent_id,
            "decision": decision.value,
            "reason": reason,
            "criteria_snapshot": json.dumps(list(criteria_snapshot)),
            "recorded_at": recorded_at_utc,
            "metadata": json.dumps(metadata),
        }
        row: aiosqlite.Row | None = None
        try:
            await self._db.execute("BEGIN IMMEDIATE")
            try:
                await self._db.execute(
                    """\
INSERT INTO decision_records (
    id, task_id, approval_id, executing_agent_id, reviewer_agent_id,
    decision, reason, criteria_snapshot, recorded_at, version, metadata
) VALUES (
    :id, :task_id, :approval_id, :executing_agent_id, :reviewer_agent_id,
    :decision, :reason, :criteria_snapshot, :recorded_at,
    (SELECT COALESCE(MAX(version), 0) + 1
       FROM decision_records WHERE task_id = :task_id),
    :metadata
)""",
                    params,
                )
                cursor = await self._db.execute(
                    "SELECT version FROM decision_records WHERE id = :id",
                    {"id": record_id},
                )
                row = await cursor.fetchone()
            except BaseException:
                await self._db.rollback()
                raise
            await self._db.commit()
        except sqlite3.IntegrityError as exc:
            if _is_unique_constraint_error(exc):
                msg = f"Duplicate decision record {record_id!r}"
                logger.warning(
                    PERSISTENCE_DECISION_RECORD_SAVE_FAILED,
                    record_id=record_id,
                    error=str(exc),
                )
                raise DuplicateRecordError(msg) from exc
            msg = f"Failed to save decision record {record_id!r}"
            logger.exception(
                PERSISTENCE_DECISION_RECORD_SAVE_FAILED,
                record_id=record_id,
                error=str(exc),
            )
            raise QueryError(msg) from exc
        except (sqlite3.Error, aiosqlite.Error) as exc:
            msg = f"Failed to save decision record {record_id!r}"
            logger.exception(
                PERSISTENCE_DECISION_RECORD_SAVE_FAILED,
                record_id=record_id,
                error=str(exc),
            )
            raise QueryError(msg) from exc

        if row is None:
            # Defensive: fetchone can return None under aiosqlite's type
            # signature even though a successful INSERT + SELECT of the
            # same id should always find the row.  Surface the anomaly
            # loudly rather than silently swallowing it.
            msg = (
                f"Failed to read back decision record {record_id!r} "
                "immediately after insert"
            )
            logger.error(
                PERSISTENCE_DECISION_RECORD_SAVE_FAILED,
                record_id=record_id,
                error=msg,
            )
            raise QueryError(msg)

        assigned_version = int(row["version"])
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
            metadata=metadata,
        )
        logger.debug(
            PERSISTENCE_DECISION_RECORD_SAVED,
            record_id=record_id,
            task_id=task_id,
            version=assigned_version,
        )
        return record

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
        # Runtime defense in depth: the Literal type prevents type-safe
        # callers from passing bad values, but we re-validate to guard
        # against untyped call sites.
        role_str: str = role
        if role_str == "executor":
            column = "executing_agent_id"
        elif role_str == "reviewer":
            column = "reviewer_agent_id"
        else:
            msg = f"role must be 'executor' or 'reviewer', got {role_str!r}"
            logger.warning(
                PERSISTENCE_DECISION_RECORD_QUERY_FAILED,
                agent_id=agent_id,
                role=role_str,
                error=msg,
            )
            raise ValueError(msg)
        try:
            cursor = await self._db.execute(
                f"SELECT {_COLS} FROM decision_records "  # noqa: S608
                f"WHERE {column} = ? ORDER BY recorded_at DESC",
                (agent_id,),
            )
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

        ``KeyError`` is deliberately NOT caught -- a missing column is a
        programming error (schema drift) that should surface loudly.
        """
        try:
            raw_criteria = row.get("criteria_snapshot")
            raw_metadata = row.get("metadata")
            parsed: dict[str, object] = dict(row)
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
