"""Postgres-backed MCP installations repository.

Persists :class:`McpInstallation` rows in the ``mcp_installations``
table using the shared ``AsyncConnectionPool``.  Each operation
checks out a connection via ``async with pool.connection() as conn``;
the context manager auto-commits on clean exit.
"""

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from synthorg.core.types import NotBlankStr
from synthorg.integrations.mcp_catalog.installations import McpInstallation
from synthorg.observability import get_logger
from synthorg.observability.events.integrations import (
    MCP_SERVER_INSTALLED,
    MCP_SERVER_UNINSTALLED,
)

if TYPE_CHECKING:
    from psycopg_pool import AsyncConnectionPool


logger = get_logger(__name__)


def _ensure_tz(value: datetime) -> datetime:
    """Guarantee UTC tzinfo on a ``TIMESTAMPTZ`` round-trip."""
    return value if value.tzinfo else value.replace(tzinfo=UTC)


class PostgresMcpInstallationRepository:
    """Postgres implementation of :class:`McpInstallationRepository`."""

    def __init__(self, pool: AsyncConnectionPool) -> None:
        self._pool = pool

    async def save(self, installation: McpInstallation) -> None:
        """Upsert an installation row (idempotent on catalog_entry_id)."""
        installed_at = installation.installed_at.astimezone(UTC)
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                """
                INSERT INTO mcp_installations (
                    catalog_entry_id, connection_name, installed_at
                ) VALUES (%s, %s, %s)
                ON CONFLICT (catalog_entry_id) DO UPDATE SET
                    connection_name = EXCLUDED.connection_name,
                    installed_at = EXCLUDED.installed_at
                """,
                (
                    installation.catalog_entry_id,
                    installation.connection_name,
                    installed_at,
                ),
            )
        logger.info(
            MCP_SERVER_INSTALLED,
            catalog_entry_id=installation.catalog_entry_id,
            connection_name=installation.connection_name,
            backend="postgres",
        )

    async def get(
        self,
        catalog_entry_id: NotBlankStr,
    ) -> McpInstallation | None:
        """Fetch a single installation by catalog entry id."""
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                """
                SELECT catalog_entry_id, connection_name, installed_at
                FROM mcp_installations
                WHERE catalog_entry_id = %s
                """,
                (catalog_entry_id,),
            )
            row = await cur.fetchone()
        if row is None:
            return None
        return McpInstallation(
            catalog_entry_id=NotBlankStr(row[0]),
            connection_name=(NotBlankStr(row[1]) if row[1] else None),
            installed_at=_ensure_tz(row[2]),
        )

    async def list_all(self) -> tuple[McpInstallation, ...]:
        """List all recorded installations, oldest-first."""
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                """
                SELECT catalog_entry_id, connection_name, installed_at
                FROM mcp_installations
                ORDER BY installed_at ASC
                """,
            )
            rows = await cur.fetchall()
        return tuple(
            McpInstallation(
                catalog_entry_id=NotBlankStr(row[0]),
                connection_name=(NotBlankStr(row[1]) if row[1] else None),
                installed_at=_ensure_tz(row[2]),
            )
            for row in rows
        )

    async def delete(self, catalog_entry_id: NotBlankStr) -> bool:
        """Delete an installation.  Returns ``True`` if a row was removed."""
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                "DELETE FROM mcp_installations WHERE catalog_entry_id = %s",
                (catalog_entry_id,),
            )
            deleted = cur.rowcount > 0
        if deleted:
            logger.info(
                MCP_SERVER_UNINSTALLED,
                catalog_entry_id=catalog_entry_id,
                backend="postgres",
            )
        return deleted
