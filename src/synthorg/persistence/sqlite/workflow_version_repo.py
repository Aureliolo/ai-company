"""SQLite repository implementation for WorkflowDefinitionVersion."""

import json
import sqlite3
from datetime import UTC, datetime

import aiosqlite
from pydantic import ValidationError

from synthorg.core.enums import WorkflowType
from synthorg.core.types import NotBlankStr  # noqa: TC001
from synthorg.engine.workflow.definition import WorkflowEdge, WorkflowNode
from synthorg.engine.workflow.version import WorkflowDefinitionVersion
from synthorg.observability import get_logger
from synthorg.observability.events.workflow_version import (
    WORKFLOW_VERSION_COUNT_FAILED,
    WORKFLOW_VERSION_DELETE_FAILED,
    WORKFLOW_VERSION_DELETED,
    WORKFLOW_VERSION_FETCH_FAILED,
    WORKFLOW_VERSION_LIST_FAILED,
    WORKFLOW_VERSION_LISTED,
    WORKFLOW_VERSION_SAVE_FAILED,
    WORKFLOW_VERSION_SAVED,
)
from synthorg.persistence.errors import QueryError

logger = get_logger(__name__)

_COLUMNS = (
    "definition_id, version, name, description, workflow_type, "
    "nodes, edges, created_by, saved_by, saved_at"
)

_SELECT_ONE = (
    "SELECT " + _COLUMNS + " "
    "FROM workflow_definition_versions "
    "WHERE definition_id = ? AND version = ?"
)

_SELECT_LIST = (
    "SELECT " + _COLUMNS + " "
    "FROM workflow_definition_versions "
    "WHERE definition_id = ? "
    "ORDER BY version DESC "
    "LIMIT ? OFFSET ?"
)


def _deserialize_row(
    row: aiosqlite.Row,
    context: str,
) -> WorkflowDefinitionVersion:
    """Reconstruct a version snapshot from a database row."""
    try:
        data = dict(row)
        data["workflow_type"] = WorkflowType(data["workflow_type"])
        data["nodes"] = tuple(
            WorkflowNode.model_validate(n) for n in json.loads(data["nodes"])
        )
        data["edges"] = tuple(
            WorkflowEdge.model_validate(e) for e in json.loads(data["edges"])
        )
        dt = datetime.fromisoformat(str(data["saved_at"]))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        data["saved_at"] = dt
        return WorkflowDefinitionVersion.model_validate(data)
    except (ValueError, ValidationError, json.JSONDecodeError, KeyError) as exc:
        msg = f"Failed to deserialize workflow version {context!r}"
        logger.exception(
            WORKFLOW_VERSION_FETCH_FAILED,
            context=context,
            error=str(exc),
        )
        raise QueryError(msg) from exc


class SQLiteWorkflowVersionRepository:
    """SQLite-backed workflow version snapshot repository.

    Version records are immutable.  ``save_version`` uses INSERT OR
    IGNORE for idempotency (safe for retries).

    Naive timestamps in ``saved_at`` are interpreted as UTC via
    ``replace(tzinfo=UTC)``.

    Args:
        db: An open aiosqlite connection with ``row_factory``
            set to ``aiosqlite.Row``.
    """

    def __init__(self, db: aiosqlite.Connection) -> None:
        self._db = db

    async def save_version(
        self,
        version: WorkflowDefinitionVersion,
    ) -> None:
        """Persist a version snapshot (insert only, idempotent)."""
        nodes_json = json.dumps(
            [n.model_dump(mode="json") for n in version.nodes],
        )
        edges_json = json.dumps(
            [e.model_dump(mode="json") for e in version.edges],
        )
        try:
            await self._db.execute(
                "INSERT OR IGNORE INTO workflow_definition_versions "
                "(definition_id, version, name, description, "
                "workflow_type, nodes, edges, created_by, "
                "saved_by, saved_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    version.definition_id,
                    version.version,
                    version.name,
                    version.description,
                    version.workflow_type.value,
                    nodes_json,
                    edges_json,
                    version.created_by,
                    version.saved_by,
                    version.saved_at.isoformat(),
                ),
            )
            await self._db.commit()
            logger.debug(
                WORKFLOW_VERSION_SAVED,
                definition_id=version.definition_id,
                version=version.version,
            )
        except (sqlite3.Error, aiosqlite.Error) as exc:
            msg = (
                f"Failed to save version {version.version} for {version.definition_id}"
            )
            logger.exception(
                WORKFLOW_VERSION_SAVE_FAILED,
                definition_id=version.definition_id,
                version=version.version,
                error=str(exc),
            )
            raise QueryError(msg) from exc

    async def get_version(
        self,
        definition_id: NotBlankStr,
        version: int,
    ) -> WorkflowDefinitionVersion | None:
        """Retrieve a specific version snapshot."""
        try:
            cursor = await self._db.execute(
                _SELECT_ONE,
                (definition_id, version),
            )
            row = await cursor.fetchone()
        except (sqlite3.Error, aiosqlite.Error) as exc:
            msg = f"Failed to fetch version {version} for {definition_id}"
            logger.exception(
                WORKFLOW_VERSION_FETCH_FAILED,
                definition_id=definition_id,
                version=version,
                error=str(exc),
            )
            raise QueryError(msg) from exc

        if row is None:
            return None

        return _deserialize_row(row, f"{definition_id}@v{version}")

    async def list_versions(
        self,
        definition_id: NotBlankStr,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[WorkflowDefinitionVersion, ...]:
        """List version snapshots ordered by version descending."""
        try:
            cursor = await self._db.execute(
                _SELECT_LIST,
                (definition_id, limit, offset),
            )
            rows = list(await cursor.fetchall())
        except (sqlite3.Error, aiosqlite.Error) as exc:
            msg = f"Failed to list versions for {definition_id}"
            logger.exception(
                WORKFLOW_VERSION_LIST_FAILED,
                definition_id=definition_id,
                error=str(exc),
            )
            raise QueryError(msg) from exc

        logger.debug(
            WORKFLOW_VERSION_LISTED,
            definition_id=definition_id,
            count=len(rows),
        )
        return tuple(
            _deserialize_row(r, f"{definition_id}@v{r['version']}") for r in rows
        )

    async def count_versions(
        self,
        definition_id: NotBlankStr,
    ) -> int:
        """Count version snapshots for a definition."""
        try:
            cursor = await self._db.execute(
                "SELECT COUNT(*) FROM workflow_definition_versions "
                "WHERE definition_id = ?",
                (definition_id,),
            )
            row = await cursor.fetchone()
        except (sqlite3.Error, aiosqlite.Error) as exc:
            msg = f"Failed to count versions for {definition_id}"
            logger.exception(
                WORKFLOW_VERSION_COUNT_FAILED,
                definition_id=definition_id,
                error=str(exc),
            )
            raise QueryError(msg) from exc

        return int(row[0]) if row else 0

    async def delete_versions_for_definition(
        self,
        definition_id: NotBlankStr,
    ) -> int:
        """Delete all version snapshots for a definition."""
        try:
            cursor = await self._db.execute(
                "DELETE FROM workflow_definition_versions WHERE definition_id = ?",
                (definition_id,),
            )
            await self._db.commit()
            count = cursor.rowcount
        except (sqlite3.Error, aiosqlite.Error) as exc:
            msg = f"Failed to delete versions for {definition_id}"
            logger.exception(
                WORKFLOW_VERSION_DELETE_FAILED,
                definition_id=definition_id,
                error=str(exc),
            )
            raise QueryError(msg) from exc
        else:
            logger.info(
                WORKFLOW_VERSION_DELETED,
                definition_id=definition_id,
                count=count,
            )
            return count
