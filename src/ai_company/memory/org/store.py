"""Org fact store — protocol and SQLite implementation.

Self-contained storage for organizational facts, separate from the
operational persistence layer.
"""

import contextlib
import sqlite3
from datetime import datetime
from typing import Protocol, runtime_checkable

import aiosqlite

from ai_company.core.enums import OrgFactCategory, SeniorityLevel
from ai_company.core.types import NotBlankStr
from ai_company.memory.org.errors import (
    OrgMemoryConnectionError,
    OrgMemoryQueryError,
    OrgMemoryWriteError,
)
from ai_company.memory.org.models import OrgFact, OrgFactAuthor
from ai_company.observability import get_logger
from ai_company.observability.events.org_memory import (
    ORG_MEMORY_QUERY_FAILED,
    ORG_MEMORY_WRITE_FAILED,
)

logger = get_logger(__name__)

_CREATE_TABLE_SQL = """\
CREATE TABLE IF NOT EXISTS org_facts (
    id TEXT PRIMARY KEY,
    content TEXT NOT NULL,
    category TEXT NOT NULL,
    author_agent_id TEXT,
    author_seniority TEXT,
    author_is_human INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1
)
"""

_CREATE_CATEGORY_INDEX_SQL = """\
CREATE INDEX IF NOT EXISTS idx_org_facts_category
ON org_facts (category)
"""

_CREATE_VERSION_INDEX_SQL = """\
CREATE INDEX IF NOT EXISTS idx_org_facts_version
ON org_facts (version)
"""


@runtime_checkable
class OrgFactStore(Protocol):
    """Protocol for organizational fact persistence."""

    async def connect(self) -> None:
        """Establish connection to the store."""
        ...

    async def disconnect(self) -> None:
        """Close the store connection."""
        ...

    async def save(self, fact: OrgFact) -> None:
        """Save an organizational fact.

        Args:
            fact: The fact to persist.

        Raises:
            OrgMemoryConnectionError: If not connected.
            OrgMemoryWriteError: If the save fails.
        """
        ...

    async def get(self, fact_id: str) -> OrgFact | None:
        """Get a fact by ID.

        Args:
            fact_id: The fact identifier.

        Returns:
            The fact, or ``None`` if not found.

        Raises:
            OrgMemoryConnectionError: If not connected.
            OrgMemoryQueryError: If the query fails.
        """
        ...

    async def query(
        self,
        *,
        categories: frozenset[OrgFactCategory] | None = None,
        text: str | None = None,
        limit: int = 5,
    ) -> tuple[OrgFact, ...]:
        """Query facts by category and/or text.

        Args:
            categories: Optional category filter.
            text: Optional text search (substring match).
            limit: Maximum results.

        Returns:
            Matching facts.

        Raises:
            OrgMemoryConnectionError: If not connected.
            OrgMemoryQueryError: If the query fails.
        """
        ...

    async def list_by_category(
        self,
        category: OrgFactCategory,
    ) -> tuple[OrgFact, ...]:
        """List all facts in a category.

        Args:
            category: The category to list.

        Returns:
            All facts in the category.

        Raises:
            OrgMemoryConnectionError: If not connected.
            OrgMemoryQueryError: If the query fails.
        """
        ...

    async def delete(self, fact_id: str) -> bool:
        """Delete a fact by ID.

        Args:
            fact_id: The fact identifier.

        Returns:
            ``True`` if deleted, ``False`` if not found.

        Raises:
            OrgMemoryConnectionError: If not connected.
            OrgMemoryWriteError: If the delete fails.
        """
        ...


def _row_to_org_fact(row: aiosqlite.Row) -> OrgFact:
    """Reconstruct an ``OrgFact`` from a database row.

    Args:
        row: A database row with org_facts columns.

    Returns:
        An ``OrgFact`` model instance.
    """
    author = OrgFactAuthor(
        agent_id=row["author_agent_id"],
        seniority=(
            SeniorityLevel(row["author_seniority"]) if row["author_seniority"] else None
        ),
        is_human=bool(row["author_is_human"]),
    )
    return OrgFact(
        id=row["id"],
        content=row["content"],
        category=OrgFactCategory(row["category"]),
        author=author,
        created_at=datetime.fromisoformat(row["created_at"]),
        version=row["version"],
    )


class SQLiteOrgFactStore:
    """SQLite-backed organizational fact store.

    Uses a separate database from the operational persistence layer
    to keep institutional knowledge decoupled.

    Args:
        db_path: Path to the SQLite database file (or ``:memory:``).
    """

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._db: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        """Open the SQLite database with WAL mode and ensure schema.

        Raises:
            OrgMemoryConnectionError: If the connection fails.
        """
        if self._db is not None:
            return
        try:
            self._db = await aiosqlite.connect(self._db_path)
            self._db.row_factory = aiosqlite.Row
            if self._db_path != ":memory:":
                await self._db.execute("PRAGMA journal_mode=WAL")
            await self._ensure_schema()
        except (sqlite3.Error, OSError) as exc:
            if self._db is not None:
                with contextlib.suppress(sqlite3.Error, OSError):
                    await self._db.close()
            self._db = None
            msg = f"Failed to connect to org fact store: {exc}"
            raise OrgMemoryConnectionError(msg) from exc

    async def _ensure_schema(self) -> None:
        """Create tables and indexes if they don't exist."""
        assert self._db is not None  # noqa: S101
        await self._db.execute(_CREATE_TABLE_SQL)
        await self._db.execute(_CREATE_CATEGORY_INDEX_SQL)
        await self._db.execute(_CREATE_VERSION_INDEX_SQL)
        await self._db.commit()

    async def disconnect(self) -> None:
        """Close the database connection."""
        if self._db is None:
            return
        try:
            await self._db.close()
        except sqlite3.Error, OSError:
            pass
        finally:
            self._db = None

    def _require_connected(self) -> aiosqlite.Connection:
        """Return the connection or raise if not connected.

        Raises:
            OrgMemoryConnectionError: If not connected.
        """
        if self._db is None:
            msg = "Not connected — call connect() first"
            raise OrgMemoryConnectionError(msg)
        return self._db

    async def save(self, fact: OrgFact) -> None:
        """Persist a fact to the database.

        Args:
            fact: The fact to save.

        Raises:
            OrgMemoryConnectionError: If not connected.
            OrgMemoryWriteError: If the save fails.
        """
        db = self._require_connected()
        try:
            await db.execute(
                "INSERT OR REPLACE INTO org_facts "
                "(id, content, category, author_agent_id, "
                "author_seniority, author_is_human, created_at, version) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    fact.id,
                    fact.content,
                    fact.category.value,
                    fact.author.agent_id,
                    fact.author.seniority.value if fact.author.seniority else None,
                    int(fact.author.is_human),
                    fact.created_at.isoformat(),
                    fact.version,
                ),
            )
            await db.commit()
        except sqlite3.Error as exc:
            logger.exception(
                ORG_MEMORY_WRITE_FAILED,
                fact_id=fact.id,
                error=str(exc),
            )
            msg = f"Failed to save org fact: {exc}"
            raise OrgMemoryWriteError(msg) from exc

    async def get(self, fact_id: str) -> OrgFact | None:
        """Get a fact by its ID.

        Args:
            fact_id: Fact identifier.

        Returns:
            The fact or ``None``.

        Raises:
            OrgMemoryConnectionError: If not connected.
            OrgMemoryQueryError: If the query fails.
        """
        db = self._require_connected()
        try:
            cursor = await db.execute(
                "SELECT * FROM org_facts WHERE id = ?",
                (fact_id,),
            )
            row = await cursor.fetchone()
        except sqlite3.Error as exc:
            logger.exception(
                ORG_MEMORY_QUERY_FAILED,
                fact_id=fact_id,
                error=str(exc),
            )
            msg = f"Failed to get org fact: {exc}"
            raise OrgMemoryQueryError(msg) from exc
        if row is None:
            return None
        return _row_to_org_fact(row)

    async def query(
        self,
        *,
        categories: frozenset[OrgFactCategory] | None = None,
        text: str | None = None,
        limit: int = 5,
    ) -> tuple[OrgFact, ...]:
        """Query facts by category and/or text content.

        All dynamic values are passed as parameterized query parameters.
        The ``WHERE`` clause is constructed from safe column/operator
        constants only — no user input is interpolated into SQL.

        Args:
            categories: Category filter.
            text: Text substring filter.
            limit: Maximum results.

        Returns:
            Matching facts.

        Raises:
            OrgMemoryConnectionError: If not connected.
            OrgMemoryQueryError: If the query fails.
        """
        db = self._require_connected()
        clauses: list[str] = []
        params: list[str | int] = []

        if categories is not None:
            placeholders = ",".join("?" for _ in categories)
            clauses.append(f"category IN ({placeholders})")
            params.extend(c.value for c in categories)

        if text is not None:
            clauses.append("content LIKE ?")
            params.append(f"%{text}%")

        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = f"SELECT * FROM org_facts{where} ORDER BY created_at DESC LIMIT ?"  # noqa: S608
        params.append(limit)

        try:
            cursor = await db.execute(sql, params)
            rows = await cursor.fetchall()
        except sqlite3.Error as exc:
            logger.exception(
                ORG_MEMORY_QUERY_FAILED,
                error=str(exc),
            )
            msg = f"Failed to query org facts: {exc}"
            raise OrgMemoryQueryError(msg) from exc
        return tuple(_row_to_org_fact(row) for row in rows)

    async def list_by_category(
        self,
        category: OrgFactCategory,
    ) -> tuple[OrgFact, ...]:
        """List all facts in a category.

        Args:
            category: The category to list.

        Returns:
            All facts in the category.

        Raises:
            OrgMemoryConnectionError: If not connected.
            OrgMemoryQueryError: If the query fails.
        """
        db = self._require_connected()
        try:
            cursor = await db.execute(
                "SELECT * FROM org_facts WHERE category = ? ORDER BY created_at DESC",
                (category.value,),
            )
            rows = await cursor.fetchall()
        except sqlite3.Error as exc:
            logger.exception(
                ORG_MEMORY_QUERY_FAILED,
                category=category.value,
                error=str(exc),
            )
            msg = f"Failed to list org facts by category: {exc}"
            raise OrgMemoryQueryError(msg) from exc
        return tuple(_row_to_org_fact(row) for row in rows)

    async def delete(self, fact_id: str) -> bool:
        """Delete a fact by ID.

        Args:
            fact_id: Fact identifier.

        Returns:
            ``True`` if deleted, ``False`` if not found.

        Raises:
            OrgMemoryConnectionError: If not connected.
            OrgMemoryWriteError: If the delete fails.
        """
        db = self._require_connected()
        try:
            cursor = await db.execute(
                "DELETE FROM org_facts WHERE id = ?",
                (fact_id,),
            )
            await db.commit()
        except sqlite3.Error as exc:
            logger.exception(
                ORG_MEMORY_WRITE_FAILED,
                fact_id=fact_id,
                error=str(exc),
            )
            msg = f"Failed to delete org fact: {exc}"
            raise OrgMemoryWriteError(msg) from exc
        else:
            return cursor.rowcount > 0

    @property
    def is_connected(self) -> bool:
        """Whether the store has an active connection."""
        return self._db is not None

    @property
    def backend_name(self) -> NotBlankStr:
        """Human-readable store identifier."""
        return NotBlankStr("sqlite_org_facts")
