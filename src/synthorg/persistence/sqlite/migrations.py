"""Apply the SQLite schema from ``schema.sql``.

Fresh installs apply the full schema directly.  No sequential
migrations exist yet -- when data stability is declared, adopt
Atlas for declarative migrations (diff schema.sql against the
current DB).
"""

import importlib.resources
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

    logger.info(PERSISTENCE_MIGRATION_COMPLETED)
