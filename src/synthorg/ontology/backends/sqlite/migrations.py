"""Apply the ontology SQLite schema from ``schema.sql``."""

import importlib.resources
import sqlite3

import aiosqlite

from synthorg.observability import get_logger
from synthorg.observability.events.ontology import (
    ONTOLOGY_SCHEMA_FAILED,
)
from synthorg.ontology.errors import OntologyConnectionError

logger = get_logger(__name__)


async def apply_ontology_schema(db: aiosqlite.Connection) -> None:
    """Apply the ontology schema to the database.

    Reads ``schema.sql`` from this package and executes all DDL
    statements via ``executescript``.  All statements use
    ``IF NOT EXISTS`` guards, making this call idempotent.

    Args:
        db: An open aiosqlite connection.

    Raises:
        OntologyConnectionError: If schema application fails.
    """
    try:
        schema_path = (
            importlib.resources.files("synthorg.ontology.backends.sqlite")
            / "schema.sql"
        )
        ddl = schema_path.read_text(encoding="utf-8")
        await db.executescript(ddl)
    except (sqlite3.Error, aiosqlite.Error, OSError) as exc:
        msg = "Failed to apply ontology schema"
        logger.exception(ONTOLOGY_SCHEMA_FAILED, error=str(exc))
        raise OntologyConnectionError(msg) from exc
