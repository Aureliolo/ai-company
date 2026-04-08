"""SQLite-backed org fact store with MVCC -- append-only log + snapshot."""

import contextlib
import json
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import PurePosixPath, PureWindowsPath
from typing import Literal

import aiosqlite
from pydantic import ValidationError

from synthorg.core.enums import (
    AutonomyLevel,
    OrgFactCategory,
    SeniorityLevel,
)
from synthorg.core.types import NotBlankStr
from synthorg.memory.org.errors import (
    OrgMemoryConnectionError,
    OrgMemoryQueryError,
    OrgMemoryWriteError,
)
from synthorg.memory.org.models import (
    OperationLogEntry,
    OperationLogSnapshot,
    OrgFact,
    OrgFactAuthor,
)
from synthorg.observability import get_logger
from synthorg.observability.events.org_memory import (
    ORG_MEMORY_CONNECT_FAILED,
    ORG_MEMORY_DISCONNECT_FAILED,
    ORG_MEMORY_MVCC_LOG_QUERIED,
    ORG_MEMORY_MVCC_PUBLISH_APPENDED,
    ORG_MEMORY_MVCC_RETRACT_APPENDED,
    ORG_MEMORY_MVCC_SNAPSHOT_AT_QUERIED,
    ORG_MEMORY_NOT_CONNECTED,
    ORG_MEMORY_QUERY_FAILED,
    ORG_MEMORY_ROW_PARSE_FAILED,
    ORG_MEMORY_WRITE_FAILED,
)

logger = get_logger(__name__)

# ── Schema DDL ──────────────────────────────────────────────────

_CREATE_OPERATION_LOG_SQL = """\
CREATE TABLE IF NOT EXISTS org_facts_operation_log (
    operation_id TEXT PRIMARY KEY,
    fact_id TEXT NOT NULL,
    operation_type TEXT NOT NULL CHECK(operation_type IN ('PUBLISH', 'RETRACT')),
    content TEXT,
    tags TEXT NOT NULL DEFAULT '[]',
    author_agent_id TEXT,
    author_seniority TEXT,
    author_is_human INTEGER NOT NULL DEFAULT 0,
    author_autonomy_level TEXT,
    category TEXT,
    timestamp TEXT NOT NULL,
    version INTEGER NOT NULL,
    UNIQUE(fact_id, version)
)
"""

_CREATE_OPLOG_FACT_INDEX_SQL = """\
CREATE INDEX IF NOT EXISTS idx_oplog_fact_id
ON org_facts_operation_log (fact_id)
"""

_CREATE_OPLOG_TIMESTAMP_INDEX_SQL = """\
CREATE INDEX IF NOT EXISTS idx_oplog_timestamp
ON org_facts_operation_log (timestamp)
"""

_CREATE_OPLOG_COMPOSITE_INDEX_SQL = """\
CREATE INDEX IF NOT EXISTS idx_oplog_ts_fact
ON org_facts_operation_log (timestamp, fact_id)
"""

_CREATE_SNAPSHOT_SQL = """\
CREATE TABLE IF NOT EXISTS org_facts_snapshot (
    fact_id TEXT PRIMARY KEY,
    content TEXT NOT NULL,
    category TEXT NOT NULL,
    tags TEXT NOT NULL DEFAULT '[]',
    author_agent_id TEXT,
    author_seniority TEXT,
    author_is_human INTEGER NOT NULL DEFAULT 0,
    author_autonomy_level TEXT,
    created_at TEXT NOT NULL,
    retracted_at TEXT,
    version INTEGER NOT NULL
)
"""

_CREATE_SNAPSHOT_CATEGORY_INDEX_SQL = """\
CREATE INDEX IF NOT EXISTS idx_snapshot_category
ON org_facts_snapshot (category)
"""

_CREATE_SNAPSHOT_ACTIVE_INDEX_SQL = """\
CREATE INDEX IF NOT EXISTS idx_snapshot_active
ON org_facts_snapshot (retracted_at) WHERE retracted_at IS NULL
"""


# ── Helpers ─────────────────────────────────────────────────────


def _reject_traversal(db_path: str) -> None:
    """Reject paths containing ``..`` traversal components.

    Args:
        db_path: Database file path to validate.

    Raises:
        OrgMemoryConnectionError: If traversal is detected.
    """
    if db_path == ":memory:":
        return
    for cls in (PurePosixPath, PureWindowsPath):
        if ".." in cls(db_path).parts:
            msg = f"Path traversal detected in db_path: {db_path!r}"
            logger.warning(
                ORG_MEMORY_CONNECT_FAILED,
                db_path=db_path,
                reason="path traversal",
            )
            raise OrgMemoryConnectionError(msg)


def _tags_to_json(tags: tuple[NotBlankStr, ...]) -> str:
    """Serialize tags tuple to sorted JSON array."""
    return json.dumps(sorted(tags))


def _tags_from_json(raw: str) -> tuple[NotBlankStr, ...]:
    """Deserialize JSON array to tags tuple.

    Args:
        raw: JSON string expected to be an array of strings.

    Returns:
        Tuple of non-blank tag strings.

    Raises:
        OrgMemoryQueryError: If the JSON is not a list.
    """
    parsed = json.loads(raw)
    if not isinstance(parsed, list):
        msg = f"Tags must be a JSON array, got {type(parsed).__name__}"
        logger.warning(ORG_MEMORY_ROW_PARSE_FAILED, error=msg)
        raise OrgMemoryQueryError(msg)
    if any(not isinstance(t, str) or not t.strip() for t in parsed):
        msg = "Tags must be a JSON array of non-blank strings"
        logger.warning(ORG_MEMORY_ROW_PARSE_FAILED, error=msg)
        raise OrgMemoryQueryError(msg)
    return tuple(NotBlankStr(t) for t in parsed)


def _parse_timestamp(raw: str) -> datetime:
    """Parse an ISO timestamp, defaulting to UTC if naive."""
    dt = datetime.fromisoformat(raw)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt


def _snapshot_row_to_org_fact(row: aiosqlite.Row) -> OrgFact:
    """Reconstruct an ``OrgFact`` from a snapshot row.

    Args:
        row: A database row with org_facts_snapshot columns.

    Returns:
        An ``OrgFact`` model instance.

    Raises:
        OrgMemoryQueryError: If the row cannot be deserialized.
    """
    try:
        created_at = _parse_timestamp(row["created_at"])
        author = OrgFactAuthor(
            agent_id=row["author_agent_id"],
            seniority=(
                SeniorityLevel(row["author_seniority"])
                if row["author_seniority"]
                else None
            ),
            autonomy_level=(
                AutonomyLevel(row["author_autonomy_level"])
                if row["author_autonomy_level"]
                else None
            ),
            is_human=bool(row["author_is_human"]),
        )
        return OrgFact(
            id=row["fact_id"],
            content=row["content"],
            category=OrgFactCategory(row["category"]),
            tags=_tags_from_json(row["tags"]),
            author=author,
            created_at=created_at,
        )
    except (KeyError, ValueError, ValidationError, OrgMemoryQueryError) as exc:
        logger.warning(
            ORG_MEMORY_ROW_PARSE_FAILED,
            error=str(exc),
            error_type=type(exc).__name__,
        )
        msg = f"Failed to deserialize snapshot row: {exc}"
        raise OrgMemoryQueryError(msg) from exc


def _row_to_operation_log_entry(
    row: aiosqlite.Row,
) -> OperationLogEntry:
    """Reconstruct an ``OperationLogEntry`` from a database row.

    Args:
        row: A database row with org_facts_operation_log columns.

    Returns:
        An ``OperationLogEntry`` model instance.

    Raises:
        OrgMemoryQueryError: If the row cannot be deserialized.
    """
    try:
        return OperationLogEntry(
            operation_id=row["operation_id"],
            fact_id=row["fact_id"],
            operation_type=row["operation_type"],
            content=row["content"],
            category=(OrgFactCategory(row["category"]) if row["category"] else None),
            tags=_tags_from_json(row["tags"]),
            author_agent_id=row["author_agent_id"],
            author_seniority=(
                SeniorityLevel(row["author_seniority"])
                if row["author_seniority"]
                else None
            ),
            author_is_human=bool(row["author_is_human"]),
            author_autonomy_level=(
                AutonomyLevel(row["author_autonomy_level"])
                if row["author_autonomy_level"]
                else None
            ),
            timestamp=_parse_timestamp(row["timestamp"]),
            version=row["version"],
        )
    except (KeyError, ValueError, ValidationError, OrgMemoryQueryError) as exc:
        logger.warning(
            ORG_MEMORY_ROW_PARSE_FAILED,
            error=str(exc),
            error_type=type(exc).__name__,
        )
        msg = f"Failed to deserialize operation log row: {exc}"
        raise OrgMemoryQueryError(msg) from exc


def _row_to_snapshot(row: aiosqlite.Row) -> OperationLogSnapshot:
    """Reconstruct an ``OperationLogSnapshot`` from a time-travel query row.

    Args:
        row: A result row from the ``snapshot_at`` CTE query.

    Returns:
        An ``OperationLogSnapshot`` model instance.

    Raises:
        OrgMemoryQueryError: If the row cannot be deserialized.
    """
    try:
        op_type: str = row["operation_type"]
        retracted_at = (
            _parse_timestamp(row["timestamp"]) if op_type == "RETRACT" else None
        )
        created_at_raw: str | None = row["created_at"]
        if created_at_raw is None:
            created_at = _parse_timestamp(row["timestamp"])
        else:
            created_at = _parse_timestamp(created_at_raw)
        return OperationLogSnapshot(
            fact_id=row["fact_id"],
            content=row["content"],
            category=OrgFactCategory(row["category"]),
            tags=_tags_from_json(row["tags"]),
            created_at=created_at,
            retracted_at=retracted_at,
            version=row["version"],
        )
    except (KeyError, ValueError, ValidationError, OrgMemoryQueryError) as exc:
        logger.warning(
            ORG_MEMORY_ROW_PARSE_FAILED,
            error=str(exc),
            error_type=type(exc).__name__,
        )
        msg = f"Failed to deserialize snapshot_at row: {exc}"
        raise OrgMemoryQueryError(msg) from exc


# ── SQLite Implementation ───────────────────────────────────────


class SQLiteOrgFactStore:
    """SQLite-backed organizational fact store with MVCC.

    All writes are appended to an operation log; a materialized
    snapshot table maintains the current committed state.  Reads
    query the snapshot.  Time-travel queries replay the log.

    Uses a separate database from the operational persistence layer
    to keep institutional knowledge decoupled.

    Args:
        db_path: Path to the SQLite database file (or ``:memory:``).

    Raises:
        OrgMemoryConnectionError: If the path contains traversal.
    """

    def __init__(self, db_path: str) -> None:
        _reject_traversal(db_path)
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
                try:
                    await self._db.close()
                except (sqlite3.Error, OSError) as close_exc:
                    logger.warning(
                        ORG_MEMORY_DISCONNECT_FAILED,
                        db_path=self._db_path,
                        reason="cleanup close during failed connect",
                        error=str(close_exc),
                        error_type=type(close_exc).__name__,
                    )
            self._db = None
            msg = f"Failed to connect to org fact store: {exc}"
            logger.exception(
                ORG_MEMORY_CONNECT_FAILED,
                db_path=self._db_path,
                error=str(exc),
            )
            raise OrgMemoryConnectionError(msg) from exc

    async def _ensure_schema(self) -> None:
        """Create tables and indexes if they don't exist."""
        db = self._require_connected()
        await db.execute(_CREATE_OPERATION_LOG_SQL)
        await db.execute(_CREATE_OPLOG_FACT_INDEX_SQL)
        await db.execute(_CREATE_OPLOG_TIMESTAMP_INDEX_SQL)
        await db.execute(_CREATE_OPLOG_COMPOSITE_INDEX_SQL)
        await db.execute(_CREATE_SNAPSHOT_SQL)
        await db.execute(_CREATE_SNAPSHOT_CATEGORY_INDEX_SQL)
        await db.execute(_CREATE_SNAPSHOT_ACTIVE_INDEX_SQL)
        await db.commit()

    async def disconnect(self) -> None:
        """Close the database connection."""
        if self._db is None:
            return
        try:
            await self._db.close()
        except (sqlite3.Error, OSError) as exc:
            logger.warning(
                ORG_MEMORY_DISCONNECT_FAILED,
                db_path=self._db_path,
                error=str(exc),
                error_type=type(exc).__name__,
            )
        finally:
            self._db = None

    def _require_connected(self) -> aiosqlite.Connection:
        """Return the connection or raise if not connected.

        Raises:
            OrgMemoryConnectionError: If not connected.
        """
        if self._db is None:
            msg = "Not connected -- call connect() first"
            logger.warning(
                ORG_MEMORY_NOT_CONNECTED,
                db_path=self._db_path,
            )
            raise OrgMemoryConnectionError(msg)
        return self._db

    # ── Write operations ────────────────────────────────────────

    async def _append_to_operation_log(  # noqa: PLR0913
        self,
        db: aiosqlite.Connection,
        *,
        fact_id: str,
        operation_type: Literal["PUBLISH", "RETRACT"],
        content: str | None,
        category: OrgFactCategory | None,
        tags: tuple[NotBlankStr, ...],
        author_agent_id: str | None,
        author_seniority: SeniorityLevel | None,
        author_is_human: bool,
        author_autonomy_level: AutonomyLevel | None,
    ) -> tuple[int, datetime]:
        """Append an operation to the log within the caller's transaction.

        Must be called inside a ``BEGIN IMMEDIATE`` transaction
        managed by the caller.

        Args:
            db: Active database connection (caller-managed txn).
            fact_id: Logical fact identifier.
            operation_type: ``PUBLISH`` or ``RETRACT``.
            content: Fact body (``None`` for RETRACT).
            category: Fact category at time of operation.
            tags: Metadata tags.
            author_agent_id: Agent ID (``None`` for human).
            author_seniority: Agent seniority level.
            author_is_human: Whether the author is human.
            author_autonomy_level: Autonomy level at write time.

        Returns:
            Tuple of ``(version, timestamp)``.
        """
        operation_id = str(uuid.uuid4())
        now = datetime.now(UTC)
        cursor = await db.execute(
            "SELECT COALESCE(MAX(version), 0) "
            "FROM org_facts_operation_log WHERE fact_id = ?",
            (fact_id,),
        )
        row = await cursor.fetchone()
        # COALESCE(MAX(version), 0) always returns exactly one row.
        current: int = row[0] if row is not None else 0
        next_version = current + 1
        await db.execute(
            "INSERT INTO org_facts_operation_log "
            "(operation_id, fact_id, operation_type, content, "
            "tags, author_agent_id, author_seniority, "
            "author_is_human, author_autonomy_level, category, "
            "timestamp, version) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                operation_id,
                fact_id,
                operation_type,
                content,
                _tags_to_json(tags),
                author_agent_id,
                (author_seniority.value if author_seniority else None),
                int(author_is_human),
                (author_autonomy_level.value if author_autonomy_level else None),
                (category.value if category else None),
                now.isoformat(),
                next_version,
            ),
        )
        return next_version, now

    async def save(self, fact: OrgFact) -> None:
        """Publish a fact: append PUBLISH to log, upsert snapshot.

        Re-publishing a fact with the same ``fact_id`` creates a
        new version in the operation log and updates the snapshot.

        Args:
            fact: The fact to persist.

        Raises:
            OrgMemoryConnectionError: If not connected.
            OrgMemoryWriteError: If the save fails.
        """
        db = self._require_connected()
        try:
            await db.execute("BEGIN IMMEDIATE")
            version, _ = await self._append_to_operation_log(
                db,
                fact_id=fact.id,
                operation_type="PUBLISH",
                content=fact.content,
                category=fact.category,
                tags=fact.tags,
                author_agent_id=fact.author.agent_id,
                author_seniority=fact.author.seniority,
                author_is_human=fact.author.is_human,
                author_autonomy_level=fact.author.autonomy_level,
            )
            await db.execute(
                "INSERT INTO org_facts_snapshot "
                "(fact_id, content, category, tags, "
                "author_agent_id, author_seniority, author_is_human, "
                "author_autonomy_level, created_at, retracted_at, "
                "version) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?) "
                "ON CONFLICT(fact_id) DO UPDATE SET "
                "content=excluded.content, "
                "category=excluded.category, "
                "tags=excluded.tags, "
                "author_agent_id=excluded.author_agent_id, "
                "author_seniority=excluded.author_seniority, "
                "author_is_human=excluded.author_is_human, "
                "author_autonomy_level=excluded.author_autonomy_level, "
                "retracted_at=NULL, "
                "version=excluded.version",
                (
                    fact.id,
                    fact.content,
                    fact.category.value,
                    _tags_to_json(fact.tags),
                    fact.author.agent_id,
                    (fact.author.seniority.value if fact.author.seniority else None),
                    int(fact.author.is_human),
                    (
                        fact.author.autonomy_level.value
                        if fact.author.autonomy_level
                        else None
                    ),
                    (
                        fact.created_at.astimezone(UTC).isoformat()
                        if fact.created_at.tzinfo is not None
                        else fact.created_at.replace(tzinfo=UTC).isoformat()
                    ),
                    version,
                ),
            )
            await db.commit()
        except sqlite3.Error as exc:
            with contextlib.suppress(sqlite3.Error):
                await db.execute("ROLLBACK")
            logger.exception(
                ORG_MEMORY_WRITE_FAILED,
                fact_id=fact.id,
                error=str(exc),
            )
            msg = f"Failed to save org fact: {exc}"
            raise OrgMemoryWriteError(msg) from exc
        else:
            logger.info(
                ORG_MEMORY_MVCC_PUBLISH_APPENDED,
                fact_id=fact.id,
                version=version,
            )

    async def delete(
        self,
        fact_id: NotBlankStr,
        *,
        author: OrgFactAuthor,
    ) -> bool:
        """Retract a fact: append RETRACT to log, mark snapshot.

        The provided ``author`` is recorded as the actor who
        performed the retraction (not the original publisher).

        Args:
            fact_id: Fact identifier.
            author: The author performing the retraction.

        Returns:
            ``True`` if retracted, ``False`` if not found or
            already retracted.

        Raises:
            OrgMemoryConnectionError: If not connected.
            OrgMemoryWriteError: If the retraction fails.
        """
        db = self._require_connected()
        try:
            await db.execute("BEGIN IMMEDIATE")
            cursor = await db.execute(
                "SELECT fact_id, category, tags "
                "FROM org_facts_snapshot "
                "WHERE fact_id = ? AND retracted_at IS NULL",
                (fact_id,),
            )
            row = await cursor.fetchone()
            if row is None:
                await db.execute("ROLLBACK")
                return False
            version, now = await self._append_to_operation_log(
                db,
                fact_id=fact_id,
                operation_type="RETRACT",
                content=None,
                category=(
                    OrgFactCategory(row["category"]) if row["category"] else None
                ),
                tags=_tags_from_json(row["tags"]),
                author_agent_id=author.agent_id,
                author_seniority=author.seniority,
                author_is_human=author.is_human,
                author_autonomy_level=author.autonomy_level,
            )
            await db.execute(
                "UPDATE org_facts_snapshot "
                "SET retracted_at = ?, version = ? "
                "WHERE fact_id = ?",
                (now.isoformat(), version, fact_id),
            )
            await db.commit()
        except sqlite3.Error as exc:
            with contextlib.suppress(sqlite3.Error):
                await db.execute("ROLLBACK")
            logger.exception(
                ORG_MEMORY_WRITE_FAILED,
                fact_id=fact_id,
                error=str(exc),
            )
            msg = f"Failed to delete org fact: {exc}"
            raise OrgMemoryWriteError(msg) from exc
        else:
            logger.info(
                ORG_MEMORY_MVCC_RETRACT_APPENDED,
                fact_id=fact_id,
                version=version,
            )
            return True

    # ── Read operations ─────────────────────────────────────────

    async def get(self, fact_id: NotBlankStr) -> OrgFact | None:
        """Get an active fact by its ID.

        Args:
            fact_id: Fact identifier.

        Returns:
            The fact or ``None`` if not found or retracted.

        Raises:
            OrgMemoryConnectionError: If not connected.
            OrgMemoryQueryError: If the query fails.
        """
        db = self._require_connected()
        try:
            cursor = await db.execute(
                "SELECT * FROM org_facts_snapshot "
                "WHERE fact_id = ? AND retracted_at IS NULL",
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
        return _snapshot_row_to_org_fact(row)

    async def query(
        self,
        *,
        categories: frozenset[OrgFactCategory] | None = None,
        text: str | None = None,
        limit: int = 5,
    ) -> tuple[OrgFact, ...]:
        """Query active facts by category and/or text content.

        All dynamic values are passed as parameterized query parameters.

        Args:
            categories: Category filter.
            text: Text substring filter.
            limit: Maximum results.

        Returns:
            Matching active facts.

        Raises:
            OrgMemoryConnectionError: If not connected.
            OrgMemoryQueryError: If the query fails.
        """
        db = self._require_connected()
        clauses: list[str] = ["retracted_at IS NULL"]
        params: list[str | int] = []

        if categories is not None and categories:
            placeholders = ",".join("?" for _ in categories)
            clauses.append(f"category IN ({placeholders})")
            params.extend(c.value for c in categories)

        escaped = ""
        if text is not None:
            escaped = text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            clauses.append("content LIKE ? ESCAPE '\\'")
            params.append(f"%{escaped}%")

        where = f" WHERE {' AND '.join(clauses)}"
        if text is not None:
            order = (
                "ORDER BY INSTR(LOWER(content), LOWER(?)) ASC, "
                "LENGTH(content) ASC, created_at DESC"
            )
            params.append(text)
        else:
            order = "ORDER BY created_at DESC"
        sql = f"SELECT * FROM org_facts_snapshot{where} {order} LIMIT ?"  # noqa: S608
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
        return tuple(_snapshot_row_to_org_fact(row) for row in rows)

    async def list_by_category(
        self,
        category: OrgFactCategory,
    ) -> tuple[OrgFact, ...]:
        """List all active facts in a category.

        Args:
            category: The category to list.

        Returns:
            Active facts in the category.

        Raises:
            OrgMemoryConnectionError: If not connected.
            OrgMemoryQueryError: If the query fails.
        """
        db = self._require_connected()
        try:
            cursor = await db.execute(
                "SELECT * FROM org_facts_snapshot "
                "WHERE category = ? AND retracted_at IS NULL "
                "ORDER BY created_at DESC",
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
        return tuple(_snapshot_row_to_org_fact(row) for row in rows)

    # ── Time-travel queries ─────────────────────────────────────

    async def snapshot_at(
        self,
        timestamp: datetime,
    ) -> tuple[OperationLogSnapshot, ...]:
        """Point-in-time snapshot of all facts at a given timestamp.

        Reconstructs fact state from the operation log.  Active facts
        have ``retracted_at=None``; retracted facts carry the retract
        timestamp.

        Args:
            timestamp: UTC timestamp for the snapshot.

        Returns:
            Snapshot entries as they existed at the given time.

        Raises:
            OrgMemoryConnectionError: If not connected.
            OrgMemoryQueryError: If the query fails.
        """
        db = self._require_connected()
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=UTC)
        else:
            timestamp = timestamp.astimezone(UTC)
        query_ts = timestamp.isoformat()
        # Time-travel CTE: reconstruct fact state at a timestamp.
        # 1. latest_ops: find the most recent operation per fact_id
        #    before the query timestamp via ROW_NUMBER window.
        # 2. Main query: for RETRACT ops (NULL content), fall back
        #    to the most recent PUBLISH content/tags.  Derive
        #    created_at from the earliest PUBLISH timestamp.
        sql = """\
WITH latest_ops AS (
    SELECT fact_id, operation_type, content, tags, category,
           timestamp, version,
           ROW_NUMBER() OVER (
               PARTITION BY fact_id ORDER BY version DESC
           ) AS rn
    FROM org_facts_operation_log
    WHERE timestamp <= ?
)
SELECT lo.fact_id, lo.operation_type,
       COALESCE(lo.content,
           (SELECT p.content FROM org_facts_operation_log p
            WHERE p.fact_id = lo.fact_id
              AND p.operation_type = 'PUBLISH'
              AND p.timestamp <= ?
            ORDER BY p.version DESC LIMIT 1)
       ) AS content,
       COALESCE(lo.category,
           (SELECT p.category FROM org_facts_operation_log p
            WHERE p.fact_id = lo.fact_id
              AND p.operation_type = 'PUBLISH'
              AND p.timestamp <= ?
            ORDER BY p.version DESC LIMIT 1)
       ) AS category,
       COALESCE(
           CASE WHEN lo.operation_type = 'PUBLISH' THEN lo.tags END,
           (SELECT p.tags FROM org_facts_operation_log p
            WHERE p.fact_id = lo.fact_id
              AND p.operation_type = 'PUBLISH'
              AND p.timestamp <= ?
            ORDER BY p.version DESC LIMIT 1)
       ) AS tags,
       lo.version, lo.timestamp,
       (SELECT MIN(timestamp)
        FROM org_facts_operation_log
        WHERE fact_id = lo.fact_id
          AND operation_type = 'PUBLISH'
          AND timestamp <= ?) AS created_at
FROM latest_ops lo
WHERE lo.rn = 1
ORDER BY lo.fact_id
"""
        try:
            cursor = await db.execute(
                sql,
                (query_ts, query_ts, query_ts, query_ts, query_ts),
            )
            rows = await cursor.fetchall()
        except sqlite3.Error as exc:
            logger.exception(
                ORG_MEMORY_QUERY_FAILED,
                timestamp=query_ts,
                error=str(exc),
            )
            msg = f"Failed to query snapshot at {query_ts}: {exc}"
            raise OrgMemoryQueryError(msg) from exc
        else:
            result = tuple(_row_to_snapshot(row) for row in rows)
            logger.debug(
                ORG_MEMORY_MVCC_SNAPSHOT_AT_QUERIED,
                timestamp=query_ts,
                count=len(result),
            )
            return result

    async def get_operation_log(
        self,
        fact_id: NotBlankStr,
    ) -> tuple[OperationLogEntry, ...]:
        """Retrieve full audit trail for a fact.

        Args:
            fact_id: Fact identifier.

        Returns:
            All operations in chronological (version) order.

        Raises:
            OrgMemoryConnectionError: If not connected.
            OrgMemoryQueryError: If the query fails.
        """
        db = self._require_connected()
        try:
            cursor = await db.execute(
                "SELECT * FROM org_facts_operation_log "
                "WHERE fact_id = ? ORDER BY version ASC",
                (fact_id,),
            )
            rows = await cursor.fetchall()
        except sqlite3.Error as exc:
            logger.exception(
                ORG_MEMORY_QUERY_FAILED,
                fact_id=fact_id,
                error=str(exc),
            )
            msg = f"Failed to get operation log for {fact_id}: {exc}"
            raise OrgMemoryQueryError(msg) from exc
        else:
            result = tuple(_row_to_operation_log_entry(row) for row in rows)
            logger.debug(
                ORG_MEMORY_MVCC_LOG_QUERIED,
                fact_id=fact_id,
                count=len(result),
            )
            return result

    @property
    def is_connected(self) -> bool:
        """Whether the store has an active connection."""
        return self._db is not None

    @property
    def backend_name(self) -> NotBlankStr:
        """Human-readable store identifier."""
        return NotBlankStr("sqlite_org_facts")
