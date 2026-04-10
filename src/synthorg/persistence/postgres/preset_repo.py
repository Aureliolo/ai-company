"""Postgres implementation of the PresetRepository protocol.

This is the Postgres sibling of src/synthorg/persistence/sqlite/preset_repo.py.
Postgres stores config_json as native JSONB column.
"""

from typing import TYPE_CHECKING

import psycopg

from synthorg.core.types import NotBlankStr  # noqa: TC001
from synthorg.observability import get_logger
from synthorg.observability.events.preset import (
    PRESET_CUSTOM_COUNT_FAILED,
    PRESET_CUSTOM_DELETE_FAILED,
    PRESET_CUSTOM_DELETED,
    PRESET_CUSTOM_FETCH_FAILED,
    PRESET_CUSTOM_FETCHED,
    PRESET_CUSTOM_LIST_FAILED,
    PRESET_CUSTOM_LISTED,
    PRESET_CUSTOM_SAVE_FAILED,
    PRESET_CUSTOM_SAVED,
)
from synthorg.persistence.errors import QueryError
from synthorg.persistence.preset_repository import PresetListRow, PresetRow

if TYPE_CHECKING:
    from psycopg_pool import AsyncConnectionPool

logger = get_logger(__name__)


class PostgresPersonalityPresetRepository:
    """Postgres-backed custom personality preset repository.

    Provides CRUD operations for user-defined personality presets
    using a shared ``psycopg_pool.AsyncConnectionPool``.

    Args:
        pool: An open psycopg_pool.AsyncConnectionPool.
    """

    def __init__(self, pool: AsyncConnectionPool) -> None:
        self._pool = pool

    async def save(
        self,
        name: NotBlankStr,
        config_json: str,
        description: str,
        created_at: str,
        updated_at: str,
    ) -> None:
        """Persist a custom preset via upsert.

        Args:
            name: Lowercase preset identifier (primary key).
            config_json: Serialized ``PersonalityConfig`` as JSON.
            description: Human-readable description.
            created_at: ISO 8601 creation timestamp.
            updated_at: ISO 8601 last-update timestamp.

        Raises:
            QueryError: If the database operation fails.
        """
        try:
            async with self._pool.connection() as conn, conn.cursor() as cur:
                await cur.execute(
                    """\
INSERT INTO custom_presets (name, config_json, description,
                           created_at, updated_at)
VALUES (%s, %s, %s, %s, %s)
ON CONFLICT(name) DO UPDATE SET
    config_json=EXCLUDED.config_json,
    description=EXCLUDED.description,
    updated_at=EXCLUDED.updated_at""",
                    (name, config_json, description, created_at, updated_at),
                )
                await conn.commit()
        except psycopg.Error as exc:
            msg = f"Failed to save custom preset {name!r}"
            logger.exception(
                PRESET_CUSTOM_SAVE_FAILED,
                preset_name=name,
                error=str(exc),
            )
            raise QueryError(msg) from exc
        logger.info(PRESET_CUSTOM_SAVED, preset_name=name)

    async def get(
        self,
        name: NotBlankStr,
    ) -> PresetRow | None:
        """Retrieve a custom preset by name.

        Args:
            name: Preset identifier.

        Returns:
            A ``PresetRow`` or ``None`` if not found.

        Raises:
            QueryError: If the database query fails.
        """
        try:
            async with self._pool.connection() as conn, conn.cursor() as cur:
                await cur.execute(
                    "SELECT config_json, description, created_at, updated_at "
                    "FROM custom_presets WHERE name = %s",
                    (name,),
                )
                row = await cur.fetchone()
        except psycopg.Error as exc:
            msg = f"Failed to fetch custom preset {name!r}"
            logger.exception(
                PRESET_CUSTOM_FETCH_FAILED,
                preset_name=name,
                error=str(exc),
            )
            raise QueryError(msg) from exc

        if row is None:
            logger.debug(
                PRESET_CUSTOM_FETCHED,
                preset_name=name,
                found=False,
            )
            return None

        logger.debug(PRESET_CUSTOM_FETCHED, preset_name=name, found=True)
        return PresetRow(row[0], row[1], row[2], row[3])

    async def list_all(
        self,
    ) -> tuple[PresetListRow, ...]:
        """List all custom presets ordered by name.

        Returns:
            Tuple of ``PresetListRow`` named tuples.

        Raises:
            QueryError: If the database query fails.
        """
        try:
            async with self._pool.connection() as conn, conn.cursor() as cur:
                await cur.execute(
                    "SELECT name, config_json, description, created_at, "
                    "updated_at FROM custom_presets ORDER BY name",
                )
                rows = await cur.fetchall()
        except psycopg.Error as exc:
            msg = "Failed to list custom presets"
            logger.exception(PRESET_CUSTOM_LIST_FAILED, error=str(exc))
            raise QueryError(msg) from exc

        result = tuple(
            PresetListRow(row[0], row[1], row[2], row[3], row[4]) for row in rows
        )
        logger.debug(PRESET_CUSTOM_LISTED, count=len(result))
        return result

    async def delete(self, name: NotBlankStr) -> bool:
        """Delete a custom preset by name.

        Args:
            name: Preset identifier.

        Returns:
            ``True`` if a row was deleted, ``False`` if not found.

        Raises:
            QueryError: If the database operation fails.
        """
        try:
            async with self._pool.connection() as conn, conn.cursor() as cur:
                await cur.execute(
                    "DELETE FROM custom_presets WHERE name = %s",
                    (name,),
                )
                deleted = cur.rowcount > 0
                await conn.commit()
        except psycopg.Error as exc:
            msg = f"Failed to delete custom preset {name!r}"
            logger.exception(
                PRESET_CUSTOM_DELETE_FAILED,
                preset_name=name,
                error=str(exc),
            )
            raise QueryError(msg) from exc

        logger.info(
            PRESET_CUSTOM_DELETED,
            preset_name=name,
            deleted=deleted,
        )
        return deleted

    async def count(self) -> int:
        """Return the number of stored custom presets.

        Raises:
            QueryError: If the database query fails.
        """
        try:
            async with self._pool.connection() as conn, conn.cursor() as cur:
                await cur.execute(
                    "SELECT COUNT(*) FROM custom_presets",
                )
                row = await cur.fetchone()
        except psycopg.Error as exc:
            msg = "Failed to count custom presets"
            logger.exception(PRESET_CUSTOM_COUNT_FAILED, error=str(exc))
            raise QueryError(msg) from exc

        if row is None:
            msg = "COUNT(*) returned no row -- database driver error"
            logger.error(PRESET_CUSTOM_COUNT_FAILED, error=msg)
            raise QueryError(msg)

        result: int = row[0]
        return result
