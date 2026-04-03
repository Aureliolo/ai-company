"""SQLite implementation of the SettingsRepository protocol."""

import sqlite3

import aiosqlite

from synthorg.core.types import NotBlankStr  # noqa: TC001
from synthorg.observability import get_logger
from synthorg.observability.events.settings import (
    SETTINGS_DELETE_FAILED,
    SETTINGS_FETCH_FAILED,
    SETTINGS_SET_FAILED,
    SETTINGS_VALUE_DELETED,
    SETTINGS_VALUE_SET,
)
from synthorg.persistence.errors import QueryError

logger = get_logger(__name__)


class SQLiteSettingsRepository:
    """SQLite-backed namespaced settings repository.

    Settings are stored in the ``settings`` table with a composite
    primary key of ``(namespace, key)``.

    Args:
        db: An open aiosqlite connection with row_factory set.
    """

    def __init__(self, db: aiosqlite.Connection) -> None:
        self._db = db

    async def get(
        self,
        namespace: NotBlankStr,
        key: NotBlankStr,
    ) -> tuple[str, str] | None:
        """Retrieve (value, updated_at) or None."""
        try:
            cursor = await self._db.execute(
                "SELECT value, updated_at FROM settings "
                "WHERE namespace = ? AND key = ?",
                (namespace, key),
            )
            row = await cursor.fetchone()
        except (sqlite3.Error, aiosqlite.Error) as exc:
            msg = f"Failed to get setting {namespace}/{key}"
            logger.exception(
                SETTINGS_FETCH_FAILED,
                namespace=namespace,
                key=key,
                error=str(exc),
            )
            raise QueryError(msg) from exc
        if row is None:
            return None
        return (str(row[0]), str(row[1]))

    async def get_namespace(
        self,
        namespace: NotBlankStr,
    ) -> tuple[tuple[str, str, str], ...]:
        """Return all (key, value, updated_at) for a namespace."""
        try:
            cursor = await self._db.execute(
                "SELECT key, value, updated_at FROM settings "
                "WHERE namespace = ? ORDER BY key",
                (namespace,),
            )
            rows = await cursor.fetchall()
        except (sqlite3.Error, aiosqlite.Error) as exc:
            msg = f"Failed to get settings for namespace {namespace}"
            logger.exception(
                SETTINGS_FETCH_FAILED,
                namespace=namespace,
                error=str(exc),
            )
            raise QueryError(msg) from exc
        return tuple((str(r[0]), str(r[1]), str(r[2])) for r in rows)

    async def get_all(self) -> tuple[tuple[str, str, str, str], ...]:
        """Return all (namespace, key, value, updated_at)."""
        try:
            cursor = await self._db.execute(
                "SELECT namespace, key, value, updated_at FROM settings "
                "ORDER BY namespace, key",
            )
            rows = await cursor.fetchall()
        except (sqlite3.Error, aiosqlite.Error) as exc:
            msg = "Failed to get all settings"
            logger.exception(
                SETTINGS_FETCH_FAILED,
                error=str(exc),
            )
            raise QueryError(msg) from exc
        return tuple((str(r[0]), str(r[1]), str(r[2]), str(r[3])) for r in rows)

    async def set(
        self,
        namespace: NotBlankStr,
        key: NotBlankStr,
        value: str,
        updated_at: str,
        *,
        expected_updated_at: str | None = None,
    ) -> bool:
        """Upsert a setting.

        Args:
            namespace: Setting namespace.
            key: Setting key.
            value: Serialized setting value.
            updated_at: New ``updated_at`` timestamp.
            expected_updated_at: When provided, enforces atomic
                compare-and-swap -- the row is only updated if
                the current ``updated_at`` matches.

        Returns:
            ``True`` if the write succeeded, ``False`` if the
            compare-and-swap condition was not met.
        """
        try:
            if expected_updated_at is not None:
                cursor = await self._db.execute(
                    "UPDATE settings SET value = ?, updated_at = ? "
                    "WHERE namespace = ? AND key = ? "
                    "AND updated_at = ?",
                    (value, updated_at, namespace, key, expected_updated_at),
                )
                await self._db.commit()
                if cursor.rowcount == 0:
                    if expected_updated_at == "":
                        # No DB row yet -- try insert.
                        cursor = await self._db.execute(
                            "INSERT OR IGNORE INTO settings "
                            "(namespace, key, value, updated_at) "
                            "VALUES (?, ?, ?, ?)",
                            (namespace, key, value, updated_at),
                        )
                        await self._db.commit()
                        if cursor.rowcount == 0:
                            return False
                    else:
                        return False
            else:
                await self._db.execute(
                    "INSERT INTO settings (namespace, key, value, updated_at) "
                    "VALUES (?, ?, ?, ?) "
                    "ON CONFLICT(namespace, key) DO UPDATE SET "
                    "value=excluded.value, updated_at=excluded.updated_at",
                    (namespace, key, value, updated_at),
                )
                await self._db.commit()
        except (sqlite3.Error, aiosqlite.Error) as exc:
            msg = f"Failed to set setting {namespace}/{key}"
            logger.exception(
                SETTINGS_SET_FAILED,
                namespace=namespace,
                key=key,
                error=str(exc),
            )
            raise QueryError(msg) from exc
        logger.debug(
            SETTINGS_VALUE_SET,
            namespace=namespace,
            key=key,
        )
        return True

    async def delete(
        self,
        namespace: NotBlankStr,
        key: NotBlankStr,
    ) -> bool:
        """Delete a setting. Return True if deleted."""
        try:
            cursor = await self._db.execute(
                "DELETE FROM settings WHERE namespace = ? AND key = ?",
                (namespace, key),
            )
            await self._db.commit()
        except (sqlite3.Error, aiosqlite.Error) as exc:
            msg = f"Failed to delete setting {namespace}/{key}"
            logger.exception(
                SETTINGS_DELETE_FAILED,
                namespace=namespace,
                key=key,
                error=str(exc),
            )
            raise QueryError(msg) from exc
        deleted = cursor.rowcount > 0
        if deleted:
            logger.debug(
                SETTINGS_VALUE_DELETED,
                namespace=namespace,
                key=key,
            )
        return deleted

    async def delete_namespace(self, namespace: NotBlankStr) -> int:
        """Delete all settings in a namespace. Return count."""
        try:
            cursor = await self._db.execute(
                "DELETE FROM settings WHERE namespace = ?",
                (namespace,),
            )
            await self._db.commit()
        except (sqlite3.Error, aiosqlite.Error) as exc:
            msg = f"Failed to delete namespace {namespace}"
            logger.exception(
                SETTINGS_DELETE_FAILED,
                namespace=namespace,
                error=str(exc),
            )
            raise QueryError(msg) from exc
        count = cursor.rowcount
        logger.debug(
            SETTINGS_VALUE_DELETED,
            namespace=namespace,
            count=count,
        )
        return count
