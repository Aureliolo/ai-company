"""SQLite-backed MCP installations repository.

Persists :class:`McpInstallation` rows in the ``mcp_installations``
table. Bound to an open ``aiosqlite.Connection`` at construction.
The app wires one instance into :class:`CatalogService` whenever
the SQLite persistence backend is active; otherwise the in-memory
``InMemoryMcpInstallationRepository`` keeps the bridge mergeable
without persistence.
"""

from datetime import UTC, datetime

import aiosqlite  # noqa: TC002

from synthorg.core.types import NotBlankStr
from synthorg.integrations.mcp_catalog.installations import McpInstallation
from synthorg.observability import get_logger
from synthorg.observability.events.integrations import (
    MCP_SERVER_INSTALLED,
    MCP_SERVER_UNINSTALLED,
)

logger = get_logger(__name__)


def _parse_timestamp(raw: str | datetime) -> datetime:
    """Parse a stored timestamp into a timezone-aware datetime.

    Accepts both ISO-8601 strings (SQLite TEXT columns) and native
    ``datetime`` objects (Postgres ``TIMESTAMPTZ`` columns). Returns
    a UTC-localized datetime so downstream code can rely on tzinfo.
    """
    if isinstance(raw, datetime):
        return raw if raw.tzinfo else raw.replace(tzinfo=UTC)
    value = datetime.fromisoformat(raw)
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


class SQLiteMcpInstallationRepository:
    """SQLite implementation of :class:`McpInstallationRepository`."""

    def __init__(self, db: aiosqlite.Connection) -> None:
        """Bind the repository to an open aiosqlite connection.

        Args:
            db: An aiosqlite connection that is already open. The
                repository does not own the connection lifecycle -
                the persistence backend controls connect/disconnect.
        """
        self._db = db

    async def save(self, installation: McpInstallation) -> None:
        """Upsert an installation row.

        ``catalog_entry_id`` is the primary key so re-installing the
        same entry is an idempotent refresh that overwrites any
        previous ``connection_name`` and ``installed_at``.
        """
        installed_at_iso = installation.installed_at.astimezone(UTC).isoformat()
        await self._db.execute(
            """
            INSERT INTO mcp_installations (
                catalog_entry_id, connection_name, installed_at
            ) VALUES (?, ?, ?)
            ON CONFLICT(catalog_entry_id) DO UPDATE SET
                connection_name = excluded.connection_name,
                installed_at = excluded.installed_at
            """,
            (
                installation.catalog_entry_id,
                installation.connection_name,
                installed_at_iso,
            ),
        )
        await self._db.commit()
        logger.info(
            MCP_SERVER_INSTALLED,
            catalog_entry_id=installation.catalog_entry_id,
            connection_name=installation.connection_name,
            backend="sqlite",
        )

    async def get(
        self,
        catalog_entry_id: NotBlankStr,
    ) -> McpInstallation | None:
        """Fetch a single installation by catalog entry id."""
        async with self._db.execute(
            """
            SELECT catalog_entry_id, connection_name, installed_at
            FROM mcp_installations
            WHERE catalog_entry_id = ?
            """,
            (catalog_entry_id,),
        ) as cursor:
            row = await cursor.fetchone()
        if row is None:
            return None
        return McpInstallation(
            catalog_entry_id=NotBlankStr(row[0]),
            connection_name=(NotBlankStr(row[1]) if row[1] else None),
            installed_at=_parse_timestamp(row[2]),
        )

    async def list_all(self) -> tuple[McpInstallation, ...]:
        """List all recorded installations."""
        async with self._db.execute(
            """
            SELECT catalog_entry_id, connection_name, installed_at
            FROM mcp_installations
            ORDER BY installed_at ASC
            """,
        ) as cursor:
            rows = await cursor.fetchall()
        return tuple(
            McpInstallation(
                catalog_entry_id=NotBlankStr(row[0]),
                connection_name=(NotBlankStr(row[1]) if row[1] else None),
                installed_at=_parse_timestamp(row[2]),
            )
            for row in rows
        )

    async def delete(self, catalog_entry_id: NotBlankStr) -> bool:
        """Delete an installation.

        Returns ``True`` when a row was removed, ``False`` when the
        id was not present.
        """
        cursor = await self._db.execute(
            "DELETE FROM mcp_installations WHERE catalog_entry_id = ?",
            (catalog_entry_id,),
        )
        # Read rowcount before commit: aiosqlite's rowcount is only
        # guaranteed to reflect the just-executed statement until the
        # transaction is committed, after which it may be reset by
        # driver-internal bookkeeping.
        deleted = cursor.rowcount > 0
        await self._db.commit()
        if deleted:
            logger.info(
                MCP_SERVER_UNINSTALLED,
                catalog_entry_id=catalog_entry_id,
                backend="sqlite",
            )
        return deleted


class InMemoryMcpInstallationRepository:
    """In-memory repository for tests and no-persistence deployments.

    Emits the same observability events as the SQLite implementation
    so audit logs are consistent regardless of which backend is wired.
    Rows live only for the lifetime of the running process; the
    persistence backend is the source of truth for production.
    """

    def __init__(self) -> None:
        """Initialize the in-memory store."""
        self._store: dict[str, McpInstallation] = {}

    async def save(self, installation: McpInstallation) -> None:
        """Upsert an installation (by catalog_entry_id)."""
        self._store[installation.catalog_entry_id] = installation
        logger.info(
            MCP_SERVER_INSTALLED,
            catalog_entry_id=installation.catalog_entry_id,
            connection_name=installation.connection_name,
            backend="in_memory",
        )

    async def get(
        self,
        catalog_entry_id: NotBlankStr,
    ) -> McpInstallation | None:
        """Fetch by catalog entry id."""
        return self._store.get(catalog_entry_id)

    async def list_all(self) -> tuple[McpInstallation, ...]:
        """List all installations ordered by ``installed_at`` ASC.

        Matches the SQLite backend so behavior is consistent.
        """
        return tuple(
            sorted(self._store.values(), key=lambda i: i.installed_at),
        )

    async def delete(self, catalog_entry_id: NotBlankStr) -> bool:
        """Delete by catalog entry id."""
        removed = self._store.pop(catalog_entry_id, None) is not None
        if removed:
            logger.info(
                MCP_SERVER_UNINSTALLED,
                catalog_entry_id=catalog_entry_id,
                backend="in_memory",
            )
        return removed
