"""Postgres repository implementation for WorkflowDefinition.

Postgres-native port of ``synthorg.persistence.sqlite.workflow_definition_repo``.
Uses native JSONB for ``nodes`` and ``edges``, and native TIMESTAMPTZ for
``created_at`` / ``updated_at``. The protocol surface returns the same
Pydantic models as the SQLite backend.
"""

from typing import TYPE_CHECKING, Any

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from pydantic import ValidationError

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

if TYPE_CHECKING:
    from psycopg_pool import AsyncConnectionPool

logger = get_logger(__name__)

_SELECT_COLUMNS = """\
id, name, description, workflow_type, nodes, edges,
created_by, created_at, updated_at, version"""


def _deserialize_row(
    row: dict[str, Any],
    context_id: str,
) -> WorkflowDefinition:
    """Reconstruct a ``WorkflowDefinition`` from a Postgres dict_row.

    Postgres returns JSONB as Python list/dict (no json.loads needed),
    and TIMESTAMPTZ as timezone-aware datetime. The main work is
    reconstructing the node/edge models and enums.

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
            WorkflowNode.model_validate(n) for n in (data.get("nodes") or [])
        )
        data["edges"] = tuple(
            WorkflowEdge.model_validate(e) for e in (data.get("edges") or [])
        )
        return WorkflowDefinition.model_validate(data)
    except (ValueError, ValidationError, KeyError, TypeError) as exc:
        msg = f"Failed to deserialize workflow definition {context_id!r}"
        logger.exception(
            PERSISTENCE_WORKFLOW_DEF_DESERIALIZE_FAILED,
            definition_id=context_id,
            error=str(exc),
        )
        raise QueryError(msg) from exc


class PostgresWorkflowDefinitionRepository:
    """Postgres-backed workflow definition repository.

    Provides CRUD operations for ``WorkflowDefinition`` models using
    a shared ``psycopg_pool.AsyncConnectionPool``. Nodes and edges are
    stored as JSONB. All write operations commit immediately.

    Args:
        pool: An open psycopg_pool.AsyncConnectionPool.
    """

    def __init__(self, pool: AsyncConnectionPool) -> None:
        self._pool = pool

    async def save(self, definition: WorkflowDefinition) -> None:
        """Persist a workflow definition via upsert.

        The upsert enforces optimistic concurrency: updates only
        succeed when the existing row's version is exactly one
        behind the incoming version.

        Args:
            definition: Workflow definition model to persist.

        Raises:
            QueryError: If the database operation fails.
            VersionConflictError: If optimistic concurrency check fails.
        """
        if definition.version < 1:
            msg = (
                f"Workflow definition version must be >= 1, got"
                f" {definition.version} for {definition.id!r}"
            )
            logger.warning(
                PERSISTENCE_WORKFLOW_DEF_SAVE_FAILED,
                definition_id=definition.id,
                error=msg,
            )
            raise QueryError(msg)

        nodes_jsonb = Jsonb([n.model_dump(mode="json") for n in definition.nodes])
        edges_jsonb = Jsonb([e.model_dump(mode="json") for e in definition.edges])
        try:
            async with self._pool.connection() as conn, conn.cursor() as cur:
                if definition.version > 1:
                    # Update path: optimistic concurrency via WHERE
                    # version = incoming_version - 1.  If no row exists
                    # at all this is also a version conflict (you can't
                    # "update" a non-existent definition).
                    await cur.execute(
                        """
                        UPDATE workflow_definitions SET
                            name=%s, description=%s, workflow_type=%s,
                            nodes=%s, edges=%s, updated_at=%s, version=%s
                        WHERE id = %s AND version = %s
                        """,
                        (
                            definition.name,
                            definition.description,
                            definition.workflow_type.value,
                            nodes_jsonb,
                            edges_jsonb,
                            definition.updated_at,
                            definition.version,
                            definition.id,
                            definition.version - 1,
                        ),
                    )
                else:
                    # Create path: version == 1.  ON CONFLICT DO NOTHING
                    # so a duplicate create attempt sets rowcount to 0.
                    await cur.execute(
                        """
                        INSERT INTO workflow_definitions
                            (id, name, description, workflow_type, nodes,
                             edges, created_by, created_at, updated_at,
                             version)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT(id) DO NOTHING
                        """,
                        (
                            definition.id,
                            definition.name,
                            definition.description,
                            definition.workflow_type.value,
                            nodes_jsonb,
                            edges_jsonb,
                            definition.created_by,
                            definition.created_at,
                            definition.updated_at,
                            definition.version,
                        ),
                    )
                if cur.rowcount == 0:
                    if definition.version > 1:
                        msg = (
                            f"Version conflict saving workflow definition"
                            f" {definition.id!r}: expected version"
                            f" {definition.version - 1}, not found"
                        )
                    else:
                        msg = (
                            f"Workflow definition {definition.id!r} already"
                            f" exists: cannot create version 1 over an"
                            f" existing row"
                        )
                    logger.warning(
                        PERSISTENCE_WORKFLOW_DEF_SAVE_FAILED,
                        definition_id=definition.id,
                        error=msg,
                    )
                    raise VersionConflictError(msg)
                await conn.commit()
        except psycopg.Error as exc:
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
            async with (
                self._pool.connection() as conn,
                conn.cursor(row_factory=dict_row) as cur,
            ):
                await cur.execute(
                    f"SELECT {_SELECT_COLUMNS} FROM workflow_definitions WHERE id = %s",  # noqa: S608
                    (definition_id,),
                )
                row = await cur.fetchone()
        except psycopg.Error as exc:
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
            conditions.append("workflow_type = %s")
            params.append(workflow_type.value)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY updated_at DESC LIMIT 10000"

        try:
            async with (
                self._pool.connection() as conn,
                conn.cursor(row_factory=dict_row) as cur,
            ):
                await cur.execute(query, params)
                rows = await cur.fetchall()
        except psycopg.Error as exc:
            msg = "Failed to list workflow definitions"
            logger.exception(
                PERSISTENCE_WORKFLOW_DEF_LIST_FAILED,
                error=str(exc),
            )
            raise QueryError(msg) from exc

        definitions = tuple(
            _deserialize_row(row, str(row.get("id", "?"))) for row in rows
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
            async with self._pool.connection() as conn, conn.cursor() as cur:
                await cur.execute(
                    "DELETE FROM workflow_definitions WHERE id = %s",
                    (definition_id,),
                )
                deleted = cur.rowcount > 0
                await conn.commit()
        except psycopg.Error as exc:
            msg = f"Failed to delete workflow definition {definition_id!r}"
            logger.exception(
                PERSISTENCE_WORKFLOW_DEF_DELETE_FAILED,
                definition_id=definition_id,
                error=str(exc),
            )
            raise QueryError(msg) from exc

        logger.info(
            PERSISTENCE_WORKFLOW_DEF_DELETED,
            definition_id=definition_id,
            deleted=deleted,
        )
        return deleted
