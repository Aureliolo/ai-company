"""Apply the SQLite schema from ``schema.sql``.

Fresh installs apply the full schema directly.  No sequential
migrations exist yet -- when data stability is declared, adopt
Atlas for declarative migrations (diff schema.sql against the
current DB).
"""

import importlib.resources
import re
import sqlite3

import aiosqlite

from synthorg.observability import get_logger
from synthorg.observability.events.persistence import (
    PERSISTENCE_MIGRATION_COMPLETED,
    PERSISTENCE_MIGRATION_FAILED,
    PERSISTENCE_MIGRATION_STARTED,
)
from synthorg.persistence.errors import MigrationError

logger = get_logger(__name__)


async def apply_schema(db: aiosqlite.Connection) -> None:
    """Apply the canonical schema to a fresh database.

    Reads ``schema.sql`` from the package and executes all DDL
    statements via ``executescript``.  All statements use
    ``IF NOT EXISTS`` guards, making this call idempotent.

    .. warning::

       ``executescript`` commits any open transaction before
       executing.  Call only on a freshly opened connection
       with no pending writes.

    Args:
        db: An open aiosqlite connection.

    Raises:
        MigrationError: If schema application fails.
    """
    logger.info(PERSISTENCE_MIGRATION_STARTED)

    try:
        schema_path = (
            importlib.resources.files("synthorg.persistence.sqlite") / "schema.sql"
        )
        ddl = schema_path.read_text(encoding="utf-8")
        await db.executescript(ddl)
    except (sqlite3.Error, aiosqlite.Error, OSError) as exc:
        msg = "Failed to apply schema"
        logger.exception(PERSISTENCE_MIGRATION_FAILED, error=str(exc))
        raise MigrationError(msg) from exc

    # Incremental column additions for existing databases.
    # SQLite ADD COLUMN is idempotent when the column already exists
    # only raises if the column name conflicts -- catch and ignore.
    await _add_column_if_missing(
        db,
        "users",
        "org_roles",
        "TEXT NOT NULL DEFAULT '[]'",
    )
    await _add_column_if_missing(
        db,
        "users",
        "scoped_departments",
        "TEXT NOT NULL DEFAULT '[]'",
    )

    logger.info(PERSISTENCE_MIGRATION_COMPLETED)


_ALLOWED_TABLES = frozenset(
    {
        "users",
        "api_keys",
        "sessions",
        "login_attempts",
        "refresh_tokens",
    }
)
_ALLOWED_COLUMN_RE = re.compile(r"^[a-z_][a-z0-9_]*$")


async def _add_column_if_missing(
    db: aiosqlite.Connection,
    table: str,
    column: str,
    definition: str,
) -> None:
    """Add a column to a table if it does not already exist.

    SQLite ``ALTER TABLE ADD COLUMN`` raises ``OperationalError``
    if the column already exists.  This helper catches that error
    and ignores it; any other ``OperationalError`` is re-raised.

    Args:
        db: An open aiosqlite connection.
        table: Table name (must be in the allowlist).
        column: Column name to add (must match ``[a-z_][a-z0-9_]*``).
        definition: Column type and constraints.  Must never be
            derived from user input.
    """
    if table not in _ALLOWED_TABLES:
        msg = f"Table not in allowlist: {table!r}"
        logger.warning("migration.validation_failed", table=table, reason=msg)
        raise ValueError(msg)
    if not _ALLOWED_COLUMN_RE.fullmatch(column):
        msg = f"Invalid column name: {column!r}"
        logger.warning("migration.validation_failed", column=column, reason=msg)
        raise ValueError(msg)
    try:
        await db.execute(
            f'ALTER TABLE "{table}" ADD COLUMN "{column}" {definition}',
        )
        await db.commit()
        logger.info(
            PERSISTENCE_MIGRATION_COMPLETED,
            detail=f"Added column {table}.{column}",
        )
    except sqlite3.OperationalError as exc:
        if "duplicate column name" in str(exc).lower():
            # Column already exists -- idempotent.
            pass
        else:
            logger.exception(
                PERSISTENCE_MIGRATION_FAILED,
                detail=f"Failed to add column {table}.{column}",
            )
            msg = f"Failed to add column {table}.{column}"
            raise MigrationError(msg) from exc
