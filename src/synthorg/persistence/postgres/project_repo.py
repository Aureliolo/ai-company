"""Postgres repository implementation for Project."""

from typing import TYPE_CHECKING, Any

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from pydantic import ValidationError

from synthorg.core.enums import ProjectStatus
from synthorg.core.project import Project
from synthorg.core.types import NotBlankStr  # noqa: TC001
from synthorg.observability import get_logger
from synthorg.observability.events.persistence import (
    PERSISTENCE_PROJECT_DELETE_FAILED,
    PERSISTENCE_PROJECT_DELETED,
    PERSISTENCE_PROJECT_DESERIALIZE_FAILED,
    PERSISTENCE_PROJECT_FETCH_FAILED,
    PERSISTENCE_PROJECT_FETCHED,
    PERSISTENCE_PROJECT_LIST_FAILED,
    PERSISTENCE_PROJECT_LISTED,
    PERSISTENCE_PROJECT_SAVE_FAILED,
    PERSISTENCE_PROJECT_SAVED,
)
from synthorg.persistence.errors import QueryError

if TYPE_CHECKING:
    from psycopg_pool import AsyncConnectionPool

logger = get_logger(__name__)

_MAX_LIST_ROWS: int = 10_000


def _row_to_project(row: dict[str, Any]) -> Project:
    """Reconstruct a ``Project`` from a Postgres dict_row."""
    data = dict(row)
    data["status"] = ProjectStatus(data["status"])
    data["team"] = tuple(data.get("team") or [])
    data["task_ids"] = tuple(data.get("task_ids") or [])
    return Project.model_validate(data)


class PostgresProjectRepository:
    """Postgres-backed project repository.

    Args:
        pool: An open psycopg_pool.AsyncConnectionPool.
    """

    def __init__(self, pool: AsyncConnectionPool) -> None:
        self._pool = pool

    async def save(self, project: Project) -> None:
        """Persist a project via upsert."""
        try:
            async with self._pool.connection() as conn, conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO projects (id, name, description, team, lead,
                                          task_ids, deadline, budget, status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT(id) DO UPDATE SET
                        name=EXCLUDED.name,
                        description=EXCLUDED.description,
                        team=EXCLUDED.team,
                        lead=EXCLUDED.lead,
                        task_ids=EXCLUDED.task_ids,
                        deadline=EXCLUDED.deadline,
                        budget=EXCLUDED.budget,
                        status=EXCLUDED.status
                    """,
                    (
                        project.id,
                        project.name,
                        project.description,
                        Jsonb(list(project.team)),
                        project.lead,
                        Jsonb(list(project.task_ids)),
                        project.deadline,
                        project.budget,
                        project.status.value,
                    ),
                )
                await conn.commit()
        except psycopg.Error as exc:
            msg = f"Failed to save project {project.id!r}"
            logger.exception(
                PERSISTENCE_PROJECT_SAVE_FAILED,
                project_id=project.id,
                error=str(exc),
            )
            raise QueryError(msg) from exc
        logger.info(PERSISTENCE_PROJECT_SAVED, project_id=project.id)

    async def get(self, project_id: NotBlankStr) -> Project | None:
        """Retrieve a project by primary key."""
        try:
            async with (
                self._pool.connection() as conn,
                conn.cursor(row_factory=dict_row) as cur,
            ):
                await cur.execute("SELECT * FROM projects WHERE id = %s", (project_id,))
                row = await cur.fetchone()
        except psycopg.Error as exc:
            msg = f"Failed to fetch project {project_id!r}"
            logger.exception(
                PERSISTENCE_PROJECT_FETCH_FAILED,
                project_id=project_id,
                error=str(exc),
            )
            raise QueryError(msg) from exc
        if row is None:
            logger.debug(
                PERSISTENCE_PROJECT_FETCHED, project_id=project_id, found=False
            )
            return None
        try:
            project = _row_to_project(row)
        except (ValueError, ValidationError, KeyError) as exc:
            msg = f"Failed to deserialize project {project_id!r}"
            logger.exception(
                PERSISTENCE_PROJECT_DESERIALIZE_FAILED,
                project_id=project_id,
                error=str(exc),
            )
            raise QueryError(msg) from exc
        logger.debug(PERSISTENCE_PROJECT_FETCHED, project_id=project_id, found=True)
        return project

    async def list_projects(
        self,
        *,
        status: ProjectStatus | None = None,
        lead: NotBlankStr | None = None,
    ) -> tuple[Project, ...]:
        """List projects with optional filters."""
        query = "SELECT * FROM projects"
        conditions: list[str] = []
        params: list[str] = []

        if status is not None:
            conditions.append("status = %s")
            params.append(status.value)
        if lead is not None:
            conditions.append("lead = %s")
            params.append(lead)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += f" ORDER BY id LIMIT {_MAX_LIST_ROWS}"

        try:
            async with (
                self._pool.connection() as conn,
                conn.cursor(row_factory=dict_row) as cur,
            ):
                await cur.execute(query, params)
                rows = await cur.fetchall()
        except psycopg.Error as exc:
            msg = "Failed to list projects"
            logger.exception(PERSISTENCE_PROJECT_LIST_FAILED, error=str(exc))
            raise QueryError(msg) from exc
        try:
            projects = tuple(_row_to_project(row) for row in rows)
        except (ValueError, ValidationError, KeyError) as exc:
            msg = "Failed to deserialize projects"
            logger.exception(PERSISTENCE_PROJECT_DESERIALIZE_FAILED, error=str(exc))
            raise QueryError(msg) from exc
        logger.debug(PERSISTENCE_PROJECT_LISTED, count=len(projects))
        return projects

    async def delete(self, project_id: NotBlankStr) -> bool:
        """Delete a project by primary key."""
        try:
            async with self._pool.connection() as conn, conn.cursor() as cur:
                await cur.execute("DELETE FROM projects WHERE id = %s", (project_id,))
                deleted = cur.rowcount > 0
                await conn.commit()
        except psycopg.Error as exc:
            msg = f"Failed to delete project {project_id!r}"
            logger.exception(
                PERSISTENCE_PROJECT_DELETE_FAILED,
                project_id=project_id,
                error=str(exc),
            )
            raise QueryError(msg) from exc
        logger.info(PERSISTENCE_PROJECT_DELETED, project_id=project_id, deleted=deleted)
        return deleted
