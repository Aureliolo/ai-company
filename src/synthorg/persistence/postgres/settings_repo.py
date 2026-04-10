"""Postgres implementation of the SettingsRepository protocol.

Postgres stores ``updated_at`` as a native ``TIMESTAMPTZ`` column
(SQLite stores ISO 8601 strings).  The repository converts to and
from ISO strings at the boundary so the protocol surface --
``tuple[str, str]`` -- is identical for both backends.
"""

from datetime import UTC, datetime
from typing import TYPE_CHECKING, cast

import psycopg
from psycopg.rows import dict_row

from synthorg.core.types import NotBlankStr  # noqa: TC001

if TYPE_CHECKING:
    from psycopg_pool import AsyncConnectionPool
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


def _parse_iso(value: str) -> datetime:
    """Parse an ISO 8601 timestamp string to a tz-aware UTC datetime.

    Naive datetimes (no ``tzinfo``) are rejected -- the Postgres
    ``TIMESTAMPTZ`` column is always tz-aware and allowing naive
    values to slip in would create round-trip drift (the server would
    interpret them in its session time zone).  Values with an offset
    are normalized to UTC so round-tripped timestamps always come
    back with ``tzinfo == UTC``.
    """
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        msg = f"settings updated_at must be timezone-aware, got naive value {value!r}"
        raise ValueError(msg)
    return parsed.astimezone(UTC)


def _format_iso(value: datetime) -> str:
    """Format a tz-aware datetime as a UTC ISO 8601 string.

    Naive datetimes are rejected for the same reason as
    :func:`_parse_iso`.  Values with a non-UTC offset are normalized
    to UTC so stored timestamps and retrieved timestamps always use
    the same offset string.
    """
    if value.tzinfo is None:
        msg = (
            f"settings updated_at must be timezone-aware, got naive datetime {value!r}"
        )
        raise ValueError(msg)
    return value.astimezone(UTC).isoformat()


class PostgresSettingsRepository:
    """Postgres-backed namespaced settings repository.

    Settings are stored in the ``settings`` table with a composite
    primary key of ``(namespace, key)``.  The ``updated_at`` column is
    ``TIMESTAMPTZ`` in Postgres; the protocol surface speaks ISO 8601
    strings and this repository handles the conversion.

    Args:
        pool: An open psycopg_pool.AsyncConnectionPool.
    """

    def __init__(self, pool: AsyncConnectionPool) -> None:
        self._pool = pool

    async def get(
        self,
        namespace: NotBlankStr,
        key: NotBlankStr,
    ) -> tuple[str, str] | None:
        """Retrieve (value, updated_at) or None."""
        try:
            async with (
                self._pool.connection() as conn,
                conn.cursor(row_factory=dict_row) as cur,
            ):
                await cur.execute(
                    "SELECT value, updated_at FROM settings "
                    "WHERE namespace = %s AND key = %s",
                    (namespace, key),
                )
                row = await cur.fetchone()
        except psycopg.Error as exc:
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
        return (str(row["value"]), _format_iso(cast("datetime", row["updated_at"])))

    async def get_namespace(
        self,
        namespace: NotBlankStr,
    ) -> tuple[tuple[str, str, str], ...]:
        """Return all (key, value, updated_at) for a namespace."""
        try:
            async with (
                self._pool.connection() as conn,
                conn.cursor(row_factory=dict_row) as cur,
            ):
                await cur.execute(
                    "SELECT key, value, updated_at FROM settings "
                    "WHERE namespace = %s ORDER BY key",
                    (namespace,),
                )
                rows = await cur.fetchall()
        except psycopg.Error as exc:
            msg = f"Failed to get settings for namespace {namespace}"
            logger.exception(
                SETTINGS_FETCH_FAILED,
                namespace=namespace,
                error=str(exc),
            )
            raise QueryError(msg) from exc
        return tuple(
            (
                str(r["key"]),
                str(r["value"]),
                _format_iso(cast("datetime", r["updated_at"])),
            )
            for r in rows
        )

    async def get_all(self) -> tuple[tuple[str, str, str, str], ...]:
        """Return all (namespace, key, value, updated_at)."""
        try:
            async with (
                self._pool.connection() as conn,
                conn.cursor(row_factory=dict_row) as cur,
            ):
                await cur.execute(
                    "SELECT namespace, key, value, updated_at FROM settings "
                    "ORDER BY namespace, key"
                )
                rows = await cur.fetchall()
        except psycopg.Error as exc:
            msg = "Failed to get all settings"
            logger.exception(SETTINGS_FETCH_FAILED, error=str(exc))
            raise QueryError(msg) from exc
        return tuple(
            (
                str(r["namespace"]),
                str(r["key"]),
                str(r["value"]),
                _format_iso(cast("datetime", r["updated_at"])),
            )
            for r in rows
        )

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
            updated_at: New ``updated_at`` timestamp (ISO 8601 string).
            expected_updated_at: When provided, enforces atomic
                compare-and-swap -- the row is only updated if the
                current ``updated_at`` matches.  An empty string
                signals "only insert if no row exists".

        Returns:
            ``True`` if the write succeeded, ``False`` if the
            compare-and-swap condition was not met.
        """
        updated_at_dt = _parse_iso(updated_at)
        try:
            async with self._pool.connection() as conn, conn.cursor() as cur:
                if expected_updated_at is not None:
                    if expected_updated_at == "":
                        await cur.execute(
                            "INSERT INTO settings "
                            "(namespace, key, value, updated_at) "
                            "VALUES (%s, %s, %s, %s) "
                            "ON CONFLICT (namespace, key) DO NOTHING",
                            (namespace, key, value, updated_at_dt),
                        )
                    else:
                        expected_dt = _parse_iso(expected_updated_at)
                        await cur.execute(
                            "UPDATE settings "
                            "SET value = %s, updated_at = %s "
                            "WHERE namespace = %s AND key = %s "
                            "AND updated_at = %s",
                            (
                                value,
                                updated_at_dt,
                                namespace,
                                key,
                                expected_dt,
                            ),
                        )
                    if cur.rowcount == 0:
                        await conn.commit()
                        return False
                else:
                    await cur.execute(
                        "INSERT INTO settings "
                        "(namespace, key, value, updated_at) "
                        "VALUES (%s, %s, %s, %s) "
                        "ON CONFLICT (namespace, key) DO UPDATE SET "
                        "value = EXCLUDED.value, "
                        "updated_at = EXCLUDED.updated_at",
                        (namespace, key, value, updated_at_dt),
                    )
                await conn.commit()
        except psycopg.Error as exc:
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
            async with self._pool.connection() as conn, conn.cursor() as cur:
                await cur.execute(
                    "DELETE FROM settings WHERE namespace = %s AND key = %s",
                    (namespace, key),
                )
                deleted = cur.rowcount > 0
                await conn.commit()
        except psycopg.Error as exc:
            msg = f"Failed to delete setting {namespace}/{key}"
            logger.exception(
                SETTINGS_DELETE_FAILED,
                namespace=namespace,
                key=key,
                error=str(exc),
            )
            raise QueryError(msg) from exc
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
            async with self._pool.connection() as conn, conn.cursor() as cur:
                await cur.execute(
                    "DELETE FROM settings WHERE namespace = %s",
                    (namespace,),
                )
                count = cur.rowcount
                await conn.commit()
        except psycopg.Error as exc:
            msg = f"Failed to delete namespace {namespace}"
            logger.exception(
                SETTINGS_DELETE_FAILED,
                namespace=namespace,
                error=str(exc),
            )
            raise QueryError(msg) from exc
        logger.debug(
            SETTINGS_VALUE_DELETED,
            namespace=namespace,
            count=count,
        )
        return count
