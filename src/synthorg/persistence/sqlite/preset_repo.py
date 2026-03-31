"""SQLite repository implementation for custom personality presets."""

import sqlite3

import aiosqlite

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

logger = get_logger(__name__)

_MAX_LIST_ROWS: int = 10_000


class SQLitePersonalityPresetRepository:
    """SQLite-backed custom personality preset repository.

    Provides CRUD operations for user-defined personality presets
    using a shared ``aiosqlite.Connection``.

    Args:
        db: An open aiosqlite connection with ``row_factory``
            set to ``aiosqlite.Row``.
    """

    def __init__(self, db: aiosqlite.Connection) -> None:
        self._db = db

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
            await self._db.execute(
                """\
INSERT INTO custom_presets (name, config_json, description,
                           created_at, updated_at)
VALUES (?, ?, ?, ?, ?)
ON CONFLICT(name) DO UPDATE SET
    config_json=excluded.config_json,
    description=excluded.description,
    updated_at=excluded.updated_at""",
                (name, config_json, description, created_at, updated_at),
            )
            await self._db.commit()
        except (sqlite3.Error, aiosqlite.Error) as exc:
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
    ) -> tuple[str, str, str, str] | None:
        """Retrieve a custom preset by name.

        Args:
            name: Preset identifier.

        Returns:
            ``(config_json, description, created_at, updated_at)``
            or ``None`` if not found.

        Raises:
            QueryError: If the database query fails.
        """
        try:
            cursor = await self._db.execute(
                "SELECT config_json, description, created_at, updated_at "
                "FROM custom_presets WHERE name = ?",
                (name,),
            )
            row = await cursor.fetchone()
        except (sqlite3.Error, aiosqlite.Error) as exc:
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
        return (row[0], row[1], row[2], row[3])

    async def list_all(
        self,
    ) -> tuple[tuple[str, str, str, str, str], ...]:
        """List all custom presets ordered by name.

        Returns:
            Tuples of ``(name, config_json, description, created_at,
            updated_at)``.

        Raises:
            QueryError: If the database query fails.
        """
        try:
            cursor = await self._db.execute(
                "SELECT name, config_json, description, created_at, "  # noqa: S608
                f"updated_at FROM custom_presets ORDER BY name LIMIT {_MAX_LIST_ROWS}",
            )
            rows = await cursor.fetchall()
        except (sqlite3.Error, aiosqlite.Error) as exc:
            msg = "Failed to list custom presets"
            logger.exception(PRESET_CUSTOM_LIST_FAILED, error=str(exc))
            raise QueryError(msg) from exc
        result = tuple((row[0], row[1], row[2], row[3], row[4]) for row in rows)
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
            cursor = await self._db.execute(
                "DELETE FROM custom_presets WHERE name = ?",
                (name,),
            )
            await self._db.commit()
        except (sqlite3.Error, aiosqlite.Error) as exc:
            msg = f"Failed to delete custom preset {name!r}"
            logger.exception(
                PRESET_CUSTOM_DELETE_FAILED,
                preset_name=name,
                error=str(exc),
            )
            raise QueryError(msg) from exc
        deleted = cursor.rowcount > 0
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
            cursor = await self._db.execute(
                "SELECT COUNT(*) FROM custom_presets",
            )
            row = await cursor.fetchone()
        except (sqlite3.Error, aiosqlite.Error) as exc:
            msg = "Failed to count custom presets"
            logger.exception(PRESET_CUSTOM_COUNT_FAILED, error=str(exc))
            raise QueryError(msg) from exc
        return row[0] if row else 0
