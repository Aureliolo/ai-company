"""SQLite repository implementation for WorkflowDefinition."""

import json
import sqlite3
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from pydantic import ValidationError

if TYPE_CHECKING:
    import aiosqlite

from synthorg.core.enums import WorkflowType
from synthorg.core.types import NotBlankStr  # noqa: TC001
from synthorg.engine.workflow.definition import (
    WorkflowDefinition,
    WorkflowEdge,
    WorkflowNode,
)
from synthorg.observability import get_logger
from synthorg.observability.events.persistence import (
    PERSISTENCE_WORKFLOW_DEF_DELETE_FAILED,
    PERSISTENCE_WORKFLOW_DEF_DELETED,
    PERSISTENCE_WORKFLOW_DEF_DESERIALIZE_FAILED,
    PERSISTENCE_WORKFLOW_DEF_FETCH_FAILED,
    PERSISTENCE_WORKFLOW_DEF_FETCHED,
    PERSISTENCE_WORKFLOW_DEF_LIST_FAILED,
    PERSISTENCE_WORKFLOW_DEF_LISTED,
    PERSISTENCE_WORKFLOW_DEF_SAVE_FAILED,
    PERSISTENCE_WORKFLOW_DEF_SAVED,
)
from synthorg.persistence.errors import QueryError, VersionConflictError

logger = get_logger(__name__)

_SELECT_COLUMNS = """\
id, name, description, workflow_type, nodes, edges,
created_by, created_at, updated_at, version"""


def _parse_row_timestamps(data: dict[str, object]) -> None:
    """Parse ISO timestamps and ensure timezone awareness."""
    for field in ("created_at", "updated_at"):
        dt = datetime.fromisoformat(str(data[field]))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        data[field] = dt


def _deserialize_row(
    row: aiosqlite.Row,
    context_id: str,
) -> WorkflowDefinition:
    """Reconstruct a ``WorkflowDefinition`` from a database row.

    Args:
        row: A single database row with workflow definition columns.
        context_id: Identifier for error context logging.

    Returns:
        Validated ``WorkflowDefinition`` model instance.

    Raises:
        QueryError: If deserialization fails.
    """
    try:
        data = dict(row)
        data["workflow_type"] = WorkflowType(data["workflow_type"])
        data["nodes"] = tuple(
            WorkflowNode.model_validate(n) for n in json.loads(data["nodes"])
        )
        data["edges"] = tuple(
            WorkflowEdge.model_validate(e) for e in json.loads(data["edges"])
        )
        _parse_row_timestamps(data)
        return WorkflowDefinition.model_validate(data)
    except (ValueError, ValidationError, json.JSONDecodeError, KeyError) as exc:
        msg = f"Failed to deserialize workflow definition {context_id!r}"
        logger.exception(
            PERSISTENCE_WORKFLOW_DEF_DESERIALIZE_FAILED,
            definition_id=context_id,
            error=str(exc),
        )
        raise QueryError(msg) from exc


class SQLiteWorkflowDefinitionRepository:
    """SQLite-backed workflow definition repository.

    Provides CRUD operations for ``WorkflowDefinition`` models using
    a shared ``aiosqlite.Connection``.  Nodes and edges are stored as
    JSON arrays.  All write operations commit immediately.

    Args:
        db: An open aiosqlite connection with ``row_factory``
            set to ``aiosqlite.Row``.
    """

    def __init__(self, db: aiosqlite.Connection) -> None:
        self._db = db

    async def save(self, definition: WorkflowDefinition) -> None:
        """Persist a workflow definition via upsert.

        The upsert enforces optimistic concurrency: updates only
        succeed when the existing row's version is exactly one
        behind the incoming version.

        Args:
            definition: Workflow definition model to persist.

        Raises:
            QueryError: If the database operation fails.
        """
        nodes_json = json.dumps(
            [n.model_dump(mode="json") for n in definition.nodes],
        )
        edges_json = json.dumps(
            [e.model_dump(mode="json") for e in definition.edges],
        )
        try:
            cursor = await self._db.execute(
                """\
INSERT INTO workflow_definitions
    (id, name, description, workflow_type, nodes, edges,
     created_by, created_at, updated_at, version)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(id) DO UPDATE SET
    name=excluded.name,
    description=excluded.description,
    workflow_type=excluded.workflow_type,
    nodes=excluded.nodes,
    edges=excluded.edges,
    updated_at=excluded.updated_at,
    version=excluded.version
WHERE workflow_definitions.version = excluded.version - 1""",
                (
                    definition.id,
                    definition.name,
                    definition.description,
                    definition.workflow_type.value,
                    nodes_json,
                    edges_json,
                    definition.created_by,
                    definition.created_at.astimezone(UTC).isoformat(),
                    definition.updated_at.astimezone(UTC).isoformat(),
                    definition.version,
                ),
            )
            if cursor.rowcount == 0 and definition.version > 1:
                await self._db.rollback()
                msg = (
                    f"Version conflict saving workflow definition"
                    f" {definition.id!r}: expected version"
                    f" {definition.version - 1}, not found"
                )
                logger.warning(
                    PERSISTENCE_WORKFLOW_DEF_SAVE_FAILED,
                    definition_id=definition.id,
                    error=msg,
                )
                raise VersionConflictError(msg)
            await self._db.commit()
        except sqlite3.Error as exc:
            msg = f"Failed to save workflow definition {definition.id!r}"
            logger.exception(
                PERSISTENCE_WORKFLOW_DEF_SAVE_FAILED,
                definition_id=definition.id,
                error=str(exc),
            )
            raise QueryError(msg) from exc
        logger.info(
            PERSISTENCE_WORKFLOW_DEF_SAVED,
            definition_id=definition.id,
        )

    async def get(
        self,
        definition_id: NotBlankStr,
    ) -> WorkflowDefinition | None:
        """Retrieve a workflow definition by primary key.

        Args:
            definition_id: Unique workflow definition identifier.

        Returns:
            The matching definition, or ``None`` if not found.

        Raises:
            QueryError: If the database query or deserialization fails.
        """
        try:
            cursor = await self._db.execute(
                f"SELECT {_SELECT_COLUMNS} FROM workflow_definitions WHERE id = ?",  # noqa: S608
                (definition_id,),
            )
            row = await cursor.fetchone()
        except sqlite3.Error as exc:
            msg = f"Failed to fetch workflow definition {definition_id!r}"
            logger.exception(
                PERSISTENCE_WORKFLOW_DEF_FETCH_FAILED,
                definition_id=definition_id,
                error=str(exc),
            )
            raise QueryError(msg) from exc

        if row is None:
            logger.debug(
                PERSISTENCE_WORKFLOW_DEF_FETCHED,
                definition_id=definition_id,
                found=False,
            )
            return None

        definition = _deserialize_row(row, definition_id)
        logger.debug(
            PERSISTENCE_WORKFLOW_DEF_FETCHED,
            definition_id=definition_id,
            found=True,
        )
        return definition

    async def list_definitions(
        self,
        *,
        workflow_type: WorkflowType | None = None,
    ) -> tuple[WorkflowDefinition, ...]:
        """List workflow definitions with optional filters.

        Args:
            workflow_type: Filter by workflow type.

        Returns:
            Matching definitions as a tuple.

        Raises:
            QueryError: If the database query or deserialization fails.
        """
        query = f"SELECT {_SELECT_COLUMNS} FROM workflow_definitions"  # noqa: S608
        conditions: list[str] = []
        params: list[str] = []

        if workflow_type is not None:
            conditions.append("workflow_type = ?")
            params.append(workflow_type.value)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY updated_at DESC LIMIT 10000"

        try:
            cursor = await self._db.execute(query, params)
            rows = await cursor.fetchall()
        except sqlite3.Error as exc:
            msg = "Failed to list workflow definitions"
            logger.exception(
                PERSISTENCE_WORKFLOW_DEF_LIST_FAILED,
                error=str(exc),
            )
            raise QueryError(msg) from exc

        definitions = tuple(
            _deserialize_row(row, str(dict(row).get("id", "?"))) for row in rows
        )
        logger.debug(
            PERSISTENCE_WORKFLOW_DEF_LISTED,
            count=len(definitions),
        )
        return definitions

    async def delete(self, definition_id: NotBlankStr) -> bool:
        """Delete a workflow definition by primary key.

        Args:
            definition_id: Unique workflow definition identifier.

        Returns:
            ``True`` if a row was deleted, ``False`` if not found.

        Raises:
            QueryError: If the database operation fails.
        """
        try:
            cursor = await self._db.execute(
                "DELETE FROM workflow_definitions WHERE id = ?",
                (definition_id,),
            )
            await self._db.commit()
        except sqlite3.Error as exc:
            msg = f"Failed to delete workflow definition {definition_id!r}"
            logger.exception(
                PERSISTENCE_WORKFLOW_DEF_DELETE_FAILED,
                definition_id=definition_id,
                error=str(exc),
            )
            raise QueryError(msg) from exc

        deleted = cursor.rowcount > 0
        logger.info(
            PERSISTENCE_WORKFLOW_DEF_DELETED,
            definition_id=definition_id,
            deleted=deleted,
        )
        return deleted
