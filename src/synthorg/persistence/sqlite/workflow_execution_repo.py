"""SQLite repository implementation for WorkflowExecution."""

import json
import sqlite3
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from pydantic import ValidationError

if TYPE_CHECKING:
    import aiosqlite

from synthorg.core.enums import (
    WorkflowExecutionStatus,
    WorkflowNodeExecutionStatus,
    WorkflowNodeType,
)
from synthorg.core.types import NotBlankStr  # noqa: TC001
from synthorg.engine.workflow.execution_models import (
    WorkflowExecution,
    WorkflowNodeExecution,
)
from synthorg.observability import get_logger
from synthorg.observability.events.persistence import (
    PERSISTENCE_WORKFLOW_EXEC_DELETE_FAILED,
    PERSISTENCE_WORKFLOW_EXEC_DELETED,
    PERSISTENCE_WORKFLOW_EXEC_DESERIALIZE_FAILED,
    PERSISTENCE_WORKFLOW_EXEC_FETCH_FAILED,
    PERSISTENCE_WORKFLOW_EXEC_FETCHED,
    PERSISTENCE_WORKFLOW_EXEC_LIST_FAILED,
    PERSISTENCE_WORKFLOW_EXEC_LISTED,
    PERSISTENCE_WORKFLOW_EXEC_SAVE_FAILED,
    PERSISTENCE_WORKFLOW_EXEC_SAVED,
)
from synthorg.persistence.errors import QueryError, VersionConflictError

logger = get_logger(__name__)

_SELECT_COLUMNS = """\
id, definition_id, definition_version, status, node_executions,
activated_by, project, created_at, updated_at, completed_at,
error, version"""


def _parse_row_timestamps(data: dict[str, object]) -> None:
    """Parse ISO timestamps and ensure timezone awareness."""
    for field in ("created_at", "updated_at"):
        dt = datetime.fromisoformat(str(data[field]))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        data[field] = dt
    if data.get("completed_at") is not None:
        dt = datetime.fromisoformat(str(data["completed_at"]))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        data["completed_at"] = dt


def _deserialize_node_executions(
    raw_json: str,
) -> tuple[WorkflowNodeExecution, ...]:
    """Deserialize JSON array into WorkflowNodeExecution tuple."""
    items = json.loads(raw_json)
    return tuple(
        WorkflowNodeExecution(
            node_id=item["node_id"],
            node_type=WorkflowNodeType(item["node_type"]),
            status=WorkflowNodeExecutionStatus(item["status"]),
            task_id=item.get("task_id"),
            skipped_reason=item.get("skipped_reason"),
        )
        for item in items
    )


def _deserialize_row(
    row: aiosqlite.Row,
    context_id: str,
) -> WorkflowExecution:
    """Reconstruct a ``WorkflowExecution`` from a database row.

    Args:
        row: A single database row with execution columns.
        context_id: Identifier for error context logging.

    Returns:
        Validated ``WorkflowExecution`` model instance.

    Raises:
        QueryError: If deserialization fails.
    """
    try:
        data = dict(row)
        data["status"] = WorkflowExecutionStatus(data["status"])
        data["node_executions"] = _deserialize_node_executions(
            data["node_executions"],
        )
        _parse_row_timestamps(data)
        return WorkflowExecution.model_validate(data)
    except (ValueError, ValidationError, json.JSONDecodeError, KeyError) as exc:
        msg = f"Failed to deserialize workflow execution {context_id!r}"
        logger.exception(
            PERSISTENCE_WORKFLOW_EXEC_DESERIALIZE_FAILED,
            execution_id=context_id,
            error=str(exc),
        )
        raise QueryError(msg) from exc


class SQLiteWorkflowExecutionRepository:
    """SQLite-backed workflow execution repository.

    Provides CRUD operations for ``WorkflowExecution`` models using
    a shared ``aiosqlite.Connection``.  Node executions are stored
    as a JSON array.  All write operations commit immediately.

    Args:
        db: An open aiosqlite connection with ``row_factory``
            set to ``aiosqlite.Row``.
    """

    def __init__(self, db: aiosqlite.Connection) -> None:
        self._db = db

    async def save(self, execution: WorkflowExecution) -> None:
        """Persist a workflow execution via upsert.

        The upsert enforces optimistic concurrency: updates only
        succeed when the existing row's version is exactly one
        behind the incoming version.

        Args:
            execution: Workflow execution model to persist.

        Raises:
            VersionConflictError: If optimistic concurrency check fails.
            QueryError: If the database operation fails.
        """
        node_executions_json = json.dumps(
            [ne.model_dump(mode="json") for ne in execution.node_executions],
        )
        completed_at_iso = (
            execution.completed_at.astimezone(UTC).isoformat()
            if execution.completed_at is not None
            else None
        )
        try:
            cursor = await self._db.execute(
                """\
INSERT INTO workflow_executions
    (id, definition_id, definition_version, status, node_executions,
     activated_by, project, created_at, updated_at, completed_at,
     error, version)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(id) DO UPDATE SET
    status=excluded.status,
    node_executions=excluded.node_executions,
    updated_at=excluded.updated_at,
    completed_at=excluded.completed_at,
    error=excluded.error,
    version=excluded.version
WHERE workflow_executions.version = excluded.version - 1""",
                (
                    execution.id,
                    execution.definition_id,
                    execution.definition_version,
                    execution.status.value,
                    node_executions_json,
                    execution.activated_by,
                    execution.project,
                    execution.created_at.astimezone(UTC).isoformat(),
                    execution.updated_at.astimezone(UTC).isoformat(),
                    completed_at_iso,
                    execution.error,
                    execution.version,
                ),
            )
            if cursor.rowcount == 0 and execution.version > 1:
                await self._db.rollback()
                msg = (
                    f"Version conflict saving workflow execution"
                    f" {execution.id!r}: expected version"
                    f" {execution.version - 1}, not found"
                )
                logger.warning(
                    PERSISTENCE_WORKFLOW_EXEC_SAVE_FAILED,
                    execution_id=execution.id,
                    error=msg,
                )
                raise VersionConflictError(msg)
            await self._db.commit()
        except sqlite3.Error as exc:
            msg = f"Failed to save workflow execution {execution.id!r}"
            logger.exception(
                PERSISTENCE_WORKFLOW_EXEC_SAVE_FAILED,
                execution_id=execution.id,
                error=str(exc),
            )
            raise QueryError(msg) from exc
        logger.info(
            PERSISTENCE_WORKFLOW_EXEC_SAVED,
            execution_id=execution.id,
        )

    async def get(
        self,
        execution_id: NotBlankStr,
    ) -> WorkflowExecution | None:
        """Retrieve a workflow execution by primary key.

        Args:
            execution_id: Unique workflow execution identifier.

        Returns:
            The matching execution, or ``None`` if not found.

        Raises:
            QueryError: If the database query or deserialization fails.
        """
        try:
            cursor = await self._db.execute(
                f"SELECT {_SELECT_COLUMNS} FROM workflow_executions WHERE id = ?",  # noqa: S608
                (execution_id,),
            )
            row = await cursor.fetchone()
        except sqlite3.Error as exc:
            msg = f"Failed to fetch workflow execution {execution_id!r}"
            logger.exception(
                PERSISTENCE_WORKFLOW_EXEC_FETCH_FAILED,
                execution_id=execution_id,
                error=str(exc),
            )
            raise QueryError(msg) from exc

        if row is None:
            logger.debug(
                PERSISTENCE_WORKFLOW_EXEC_FETCHED,
                execution_id=execution_id,
                found=False,
            )
            return None

        execution = _deserialize_row(row, execution_id)
        logger.debug(
            PERSISTENCE_WORKFLOW_EXEC_FETCHED,
            execution_id=execution_id,
            found=True,
        )
        return execution

    async def list_by_definition(
        self,
        definition_id: NotBlankStr,
    ) -> tuple[WorkflowExecution, ...]:
        """List executions for a given workflow definition.

        Args:
            definition_id: The source definition identifier.

        Returns:
            Matching executions ordered by ``updated_at`` descending.

        Raises:
            QueryError: If the database query fails.
        """
        try:
            cursor = await self._db.execute(
                f"SELECT {_SELECT_COLUMNS} FROM workflow_executions"  # noqa: S608
                " WHERE definition_id = ?"
                " ORDER BY updated_at DESC LIMIT 10000",
                (definition_id,),
            )
            rows = await cursor.fetchall()
        except sqlite3.Error as exc:
            msg = f"Failed to list executions for definition {definition_id!r}"
            logger.exception(
                PERSISTENCE_WORKFLOW_EXEC_LIST_FAILED,
                definition_id=definition_id,
                error=str(exc),
            )
            raise QueryError(msg) from exc

        executions = tuple(
            _deserialize_row(row, str(dict(row).get("id", "?"))) for row in rows
        )
        logger.debug(
            PERSISTENCE_WORKFLOW_EXEC_LISTED,
            definition_id=definition_id,
            count=len(executions),
        )
        return executions

    async def list_by_status(
        self,
        status: WorkflowExecutionStatus,
    ) -> tuple[WorkflowExecution, ...]:
        """List executions with a given status.

        Args:
            status: The execution status to filter by.

        Returns:
            Matching executions ordered by ``updated_at`` descending.

        Raises:
            QueryError: If the database query fails.
        """
        try:
            cursor = await self._db.execute(
                f"SELECT {_SELECT_COLUMNS} FROM workflow_executions"  # noqa: S608
                " WHERE status = ?"
                " ORDER BY updated_at DESC LIMIT 10000",
                (status.value,),
            )
            rows = await cursor.fetchall()
        except sqlite3.Error as exc:
            msg = f"Failed to list executions with status {status.value!r}"
            logger.exception(
                PERSISTENCE_WORKFLOW_EXEC_LIST_FAILED,
                status=status.value,
                error=str(exc),
            )
            raise QueryError(msg) from exc

        executions = tuple(
            _deserialize_row(row, str(dict(row).get("id", "?"))) for row in rows
        )
        logger.debug(
            PERSISTENCE_WORKFLOW_EXEC_LISTED,
            status=status.value,
            count=len(executions),
        )
        return executions

    async def delete(self, execution_id: NotBlankStr) -> bool:
        """Delete a workflow execution by primary key.

        Args:
            execution_id: Unique workflow execution identifier.

        Returns:
            ``True`` if a row was deleted, ``False`` if not found.

        Raises:
            QueryError: If the database operation fails.
        """
        try:
            cursor = await self._db.execute(
                "DELETE FROM workflow_executions WHERE id = ?",
                (execution_id,),
            )
            await self._db.commit()
        except sqlite3.Error as exc:
            msg = f"Failed to delete workflow execution {execution_id!r}"
            logger.exception(
                PERSISTENCE_WORKFLOW_EXEC_DELETE_FAILED,
                execution_id=execution_id,
                error=str(exc),
            )
            raise QueryError(msg) from exc

        deleted = cursor.rowcount > 0
        logger.info(
            PERSISTENCE_WORKFLOW_EXEC_DELETED,
            execution_id=execution_id,
            deleted=deleted,
        )
        return deleted
