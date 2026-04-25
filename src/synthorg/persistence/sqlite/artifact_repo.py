"""SQLite repository implementation for Artifact."""

import sqlite3
from datetime import UTC, datetime

import aiosqlite
from pydantic import ValidationError

from synthorg.core.artifact import Artifact
from synthorg.core.enums import ArtifactType
from synthorg.core.types import NotBlankStr  # noqa: TC001
from synthorg.observability import get_logger
from synthorg.observability.events.persistence import (
    PERSISTENCE_ARTIFACT_DELETE_FAILED,
    PERSISTENCE_ARTIFACT_DESERIALIZE_FAILED,
    PERSISTENCE_ARTIFACT_FETCH_FAILED,
    PERSISTENCE_ARTIFACT_FETCHED,
    PERSISTENCE_ARTIFACT_LIST_FAILED,
    PERSISTENCE_ARTIFACT_LISTED,
    PERSISTENCE_ARTIFACT_SAVE_FAILED,
)
from synthorg.persistence.errors import QueryError

logger = get_logger(__name__)

_MAX_LIST_ROWS: int = 10_000


def _row_to_artifact(row: aiosqlite.Row) -> Artifact:
    """Reconstruct an ``Artifact`` from a database row.

    Args:
        row: A single database row with artifact columns.

    Returns:
        Validated ``Artifact`` model instance.
    """
    data = dict(row)
    data["type"] = ArtifactType(data["type"])
    raw_ts = data["created_at"]
    if raw_ts is not None:
        parsed = datetime.fromisoformat(raw_ts)
        # Ensure timezone-aware -- stored as UTC ISO string.
        data["created_at"] = (
            parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)
        )
    return Artifact.model_validate(data)


class SQLiteArtifactRepository:
    """SQLite-backed artifact repository.

    Provides CRUD operations for ``Artifact`` models using a shared
    ``aiosqlite.Connection``.  All write operations commit immediately.

    Args:
        db: An open aiosqlite connection with ``row_factory``
            set to ``aiosqlite.Row``.
    """

    def __init__(self, db: aiosqlite.Connection) -> None:
        self._db = db

    async def save(self, artifact: Artifact) -> None:
        """Persist an artifact via upsert (insert or update on conflict).

        Args:
            artifact: Artifact model to persist.

        Raises:
            QueryError: If the database operation fails.
        """
        try:
            await self._db.execute(
                """\
INSERT INTO artifacts (id, type, path, task_id, created_by,
                       description, content_type, size_bytes, created_at)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(id) DO UPDATE SET
    type=excluded.type,
    path=excluded.path,
    task_id=excluded.task_id,
    created_by=excluded.created_by,
    description=excluded.description,
    content_type=excluded.content_type,
    size_bytes=excluded.size_bytes,
    created_at=excluded.created_at""",
                (
                    artifact.id,
                    artifact.type.value,
                    artifact.path,
                    artifact.task_id,
                    artifact.created_by,
                    artifact.description,
                    artifact.content_type,
                    artifact.size_bytes,
                    (
                        artifact.created_at.astimezone(UTC).isoformat()
                        if artifact.created_at is not None
                        else None
                    ),
                ),
            )
            await self._db.commit()
        except (sqlite3.Error, aiosqlite.Error) as exc:
            msg = f"Failed to save artifact {artifact.id!r}"
            logger.exception(
                PERSISTENCE_ARTIFACT_SAVE_FAILED,
                artifact_id=artifact.id,
                error=str(exc),
            )
            raise QueryError(msg) from exc

    async def get(self, artifact_id: NotBlankStr) -> Artifact | None:
        """Retrieve an artifact by primary key.

        Args:
            artifact_id: Unique artifact identifier.

        Returns:
            The matching ``Artifact``, or ``None`` if not found.

        Raises:
            QueryError: If the database query or deserialization fails.
        """
        try:
            cursor = await self._db.execute(
                "SELECT * FROM artifacts WHERE id = ?", (artifact_id,)
            )
            row = await cursor.fetchone()
        except (sqlite3.Error, aiosqlite.Error) as exc:
            msg = f"Failed to fetch artifact {artifact_id!r}"
            logger.exception(
                PERSISTENCE_ARTIFACT_FETCH_FAILED,
                artifact_id=artifact_id,
                error=str(exc),
            )
            raise QueryError(msg) from exc
        if row is None:
            logger.debug(
                PERSISTENCE_ARTIFACT_FETCHED, artifact_id=artifact_id, found=False
            )
            return None
        try:
            artifact = _row_to_artifact(row)
        except (ValueError, ValidationError, KeyError) as exc:
            msg = f"Failed to deserialize artifact {artifact_id!r}"
            logger.exception(
                PERSISTENCE_ARTIFACT_DESERIALIZE_FAILED,
                artifact_id=artifact_id,
                error=str(exc),
            )
            raise QueryError(msg) from exc
        logger.debug(PERSISTENCE_ARTIFACT_FETCHED, artifact_id=artifact_id, found=True)
        return artifact

    async def list_artifacts(
        self,
        *,
        task_id: NotBlankStr | None = None,
        created_by: NotBlankStr | None = None,
        artifact_type: ArtifactType | None = None,
    ) -> tuple[Artifact, ...]:
        """List artifacts with optional filters.

        Args:
            task_id: Filter by originating task ID.
            created_by: Filter by creator agent ID.
            artifact_type: Filter by artifact type.

        Returns:
            Matching artifacts as a tuple.

        Raises:
            QueryError: If the database query or deserialization fails.
        """
        query = "SELECT * FROM artifacts"
        conditions: list[str] = []
        params: list[str] = []

        if task_id is not None:
            conditions.append("task_id = ?")
            params.append(task_id)
        if created_by is not None:
            conditions.append("created_by = ?")
            params.append(created_by)
        if artifact_type is not None:
            conditions.append("type = ?")
            params.append(artifact_type.value)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += f" ORDER BY id LIMIT {_MAX_LIST_ROWS}"

        try:
            cursor = await self._db.execute(query, params)
            rows = await cursor.fetchall()
        except (sqlite3.Error, aiosqlite.Error) as exc:
            msg = "Failed to list artifacts"
            logger.exception(PERSISTENCE_ARTIFACT_LIST_FAILED, error=str(exc))
            raise QueryError(msg) from exc
        try:
            artifacts = tuple(_row_to_artifact(row) for row in rows)
        except (ValueError, ValidationError, KeyError) as exc:
            msg = "Failed to deserialize artifacts"
            logger.exception(PERSISTENCE_ARTIFACT_DESERIALIZE_FAILED, error=str(exc))
            raise QueryError(msg) from exc
        logger.debug(PERSISTENCE_ARTIFACT_LISTED, count=len(artifacts))
        return artifacts

    async def delete(self, artifact_id: NotBlankStr) -> bool:
        """Delete an artifact by primary key.

        Args:
            artifact_id: Unique artifact identifier.

        Returns:
            ``True`` if a row was deleted, ``False`` if not found.

        Raises:
            QueryError: If the database operation fails.
        """
        try:
            cursor = await self._db.execute(
                "DELETE FROM artifacts WHERE id = ?", (artifact_id,)
            )
            await self._db.commit()
        except (sqlite3.Error, aiosqlite.Error) as exc:
            msg = f"Failed to delete artifact {artifact_id!r}"
            logger.exception(
                PERSISTENCE_ARTIFACT_DELETE_FAILED,
                artifact_id=artifact_id,
                error=str(exc),
            )
            raise QueryError(msg) from exc
        return cursor.rowcount > 0
