"""SQLite repository implementation for decision records.

Append-only: records can be appended and queried but never updated or
deleted, preserving audit integrity.
"""

import json
import sqlite3
from datetime import UTC
from typing import TYPE_CHECKING

import aiosqlite
from pydantic import ValidationError

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

if TYPE_CHECKING:
    from synthorg.core.types import NotBlankStr

logger = get_logger(__name__)

_ROLE_EXECUTOR = "executor"
_ROLE_REVIEWER = "reviewer"
_VALID_ROLES: frozenset[str] = frozenset({_ROLE_EXECUTOR, _ROLE_REVIEWER})

_COLS = (
    "id, task_id, approval_id, executing_agent_id, reviewer_agent_id, "
    "decision, reason, criteria_snapshot, recorded_at, version, metadata"
)


class SQLiteDecisionRepository:
    """SQLite implementation of the DecisionRepository protocol.

    Append-only: decision records are immutable audit entries of
    review gate decisions.  Timestamps are normalized to UTC before
    storage for consistent lexicographic ordering.

    Args:
        db: An open aiosqlite connection.
    """

    def __init__(self, db: aiosqlite.Connection) -> None:
        self._db = db

    async def append(self, record: DecisionRecord) -> None:
        """Persist a decision record (append-only, no upsert).

        Args:
            record: The decision record to persist.

        Raises:
            DuplicateRecordError: If a record with the same ID exists.
            QueryError: If the operation fails.
        """
        try:
            recorded_at_utc = record.recorded_at.astimezone(UTC).isoformat()
            await self._db.execute(
                """\
INSERT INTO decision_records (
    id, task_id, approval_id, executing_agent_id, reviewer_agent_id,
    decision, reason, criteria_snapshot, recorded_at, version, metadata
) VALUES (
    :id, :task_id, :approval_id, :executing_agent_id, :reviewer_agent_id,
    :decision, :reason, :criteria_snapshot, :recorded_at, :version, :metadata
)""",
                {
                    "id": record.id,
                    "task_id": record.task_id,
                    "approval_id": record.approval_id,
                    "executing_agent_id": record.executing_agent_id,
                    "reviewer_agent_id": record.reviewer_agent_id,
                    "decision": record.decision.value,
                    "reason": record.reason,
                    "criteria_snapshot": json.dumps(list(record.criteria_snapshot)),
                    "recorded_at": recorded_at_utc,
                    "version": record.version,
                    "metadata": json.dumps(record.metadata),
                },
            )
            await self._db.commit()
        except sqlite3.IntegrityError as exc:
            error_text = str(exc)
            is_duplicate = (
                "UNIQUE constraint failed: decision_records.id" in error_text
                or "PRIMARY KEY" in error_text
                or "decision_records.task_id" in error_text
            )
            if is_duplicate:
                msg = f"Duplicate decision record {record.id!r}"
                logger.warning(
                    PERSISTENCE_DECISION_RECORD_SAVE_FAILED,
                    record_id=record.id,
                    error=error_text,
                )
                raise DuplicateRecordError(msg) from exc
            msg = f"Failed to save decision record {record.id!r}"
            logger.exception(
                PERSISTENCE_DECISION_RECORD_SAVE_FAILED,
                record_id=record.id,
                error=error_text,
            )
            raise QueryError(msg) from exc
        except (sqlite3.Error, aiosqlite.Error) as exc:
            msg = f"Failed to save decision record {record.id!r}"
            logger.exception(
                PERSISTENCE_DECISION_RECORD_SAVE_FAILED,
                record_id=record.id,
                error=str(exc),
            )
            raise QueryError(msg) from exc
        logger.debug(
            PERSISTENCE_DECISION_RECORD_SAVED,
            record_id=record.id,
            task_id=record.task_id,
            version=record.version,
        )

    async def get(self, record_id: NotBlankStr) -> DecisionRecord | None:
        """Retrieve a decision record by ID.

        Args:
            record_id: The record identifier.

        Returns:
            The record, or ``None`` if not found.

        Raises:
            QueryError: If the operation fails.
        """
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
        """List decision records for a task ordered by version ascending.

        Args:
            task_id: The task identifier.

        Returns:
            Matching records as a tuple (oldest first).

        Raises:
            QueryError: If the operation fails.
        """
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
        role: str,
    ) -> tuple[DecisionRecord, ...]:
        """List decision records where the agent acted in the given role.

        Args:
            agent_id: The agent identifier.
            role: Either ``"executor"`` or ``"reviewer"``.

        Returns:
            Matching records as a tuple, ordered by ``recorded_at`` DESC.

        Raises:
            QueryError: If the operation fails.
            ValueError: If ``role`` is not a recognised value.
        """
        if role not in _VALID_ROLES:
            msg = f"role must be 'executor' or 'reviewer', got {role!r}"
            raise ValueError(msg)
        column = "executing_agent_id" if role == _ROLE_EXECUTOR else "reviewer_agent_id"
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

        Args:
            row: A dict mapping column names to their values.

        Raises:
            QueryError: If the row cannot be deserialized.
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
        except (ValidationError, json.JSONDecodeError, KeyError, TypeError) as exc:
            msg = f"Failed to deserialize decision record {row.get('id')!r}"
            logger.exception(
                PERSISTENCE_DECISION_RECORD_DESERIALIZE_FAILED,
                record_id=row.get("id"),
                error=str(exc),
            )
            raise QueryError(msg) from exc
