"""SQLite implementation of the OntologyBackend protocol."""

import asyncio
import json
import sqlite3
from typing import TYPE_CHECKING

import aiosqlite

from synthorg.observability import get_logger
from synthorg.observability.events.ontology import (
    ONTOLOGY_BACKEND_CONNECTED,
    ONTOLOGY_BACKEND_CONNECTING,
    ONTOLOGY_BACKEND_DISCONNECTED,
    ONTOLOGY_BACKEND_HEALTH_CHECK,
    ONTOLOGY_ENTITY_DELETED,
    ONTOLOGY_ENTITY_REGISTERED,
    ONTOLOGY_ENTITY_UPDATED,
    ONTOLOGY_SEARCH_EXECUTED,
)
from synthorg.ontology.backends.sqlite.migrations import apply_ontology_schema
from synthorg.ontology.errors import (
    OntologyConnectionError,
    OntologyDuplicateError,
    OntologyNotFoundError,
)
from synthorg.ontology.models import (
    EntityDefinition,
    EntityField,
    EntityRelation,
    EntitySource,
    EntityTier,
)

if TYPE_CHECKING:
    from synthorg.core.types import NotBlankStr

logger = get_logger(__name__)


class SQLiteOntologyBackend:
    """SQLite implementation of the OntologyBackend protocol.

    Uses a single aiosqlite connection with WAL mode for
    file-based databases.

    Args:
        db_path: Path to the SQLite database file, or ``":memory:"``
            for in-memory databases.
    """

    def __init__(self, db_path: str = ":memory:") -> None:
        self._db_path = db_path
        self._db: aiosqlite.Connection | None = None
        self._lifecycle_lock = asyncio.Lock()

    # ── Lifecycle ───────────────────────────────────────────────

    async def connect(self) -> None:
        """Establish connection, enable WAL, apply schema."""
        async with self._lifecycle_lock:
            if self._db is not None:
                return
            logger.info(ONTOLOGY_BACKEND_CONNECTING, db_path=self._db_path)
            try:
                db = await aiosqlite.connect(self._db_path)
                db.row_factory = aiosqlite.Row
                if self._db_path != ":memory:":
                    await db.execute("PRAGMA journal_mode=WAL")
                await apply_ontology_schema(db)
                self._db = db
            except OntologyConnectionError:
                raise
            except (sqlite3.Error, aiosqlite.Error, OSError) as exc:
                msg = f"Failed to connect to {self._db_path}"
                logger.exception(ONTOLOGY_BACKEND_CONNECTING, error=str(exc))
                raise OntologyConnectionError(msg) from exc
            logger.info(ONTOLOGY_BACKEND_CONNECTED, db_path=self._db_path)

    async def disconnect(self) -> None:
        """Close the database connection."""
        async with self._lifecycle_lock:
            if self._db is None:
                return
            db = self._db
            self._db = None
            await db.close()
            logger.info(ONTOLOGY_BACKEND_DISCONNECTED)

    async def health_check(self) -> bool:
        """Return True if the connection is alive."""
        if self._db is None:
            return False
        try:
            cursor = await self._db.execute("SELECT 1")
            await cursor.fetchone()
        except sqlite3.Error, aiosqlite.Error:
            logger.warning(ONTOLOGY_BACKEND_HEALTH_CHECK, healthy=False)
            return False
        logger.debug(ONTOLOGY_BACKEND_HEALTH_CHECK, healthy=True)
        return True

    @property
    def is_connected(self) -> bool:
        """Whether the backend has an active connection."""
        return self._db is not None

    @property
    def backend_name(self) -> NotBlankStr:
        """Human-readable backend identifier."""
        return "sqlite"

    # ── Helpers ──────────────────────────────────────────────────

    def _require_connected(self) -> aiosqlite.Connection:
        """Return the active connection or raise."""
        if self._db is None:
            msg = "Ontology backend is not connected"
            raise OntologyConnectionError(msg)
        return self._db

    def _row_to_entity(self, row: aiosqlite.Row) -> EntityDefinition:
        """Deserialize a database row into an EntityDefinition."""
        return EntityDefinition(
            name=row["name"],
            tier=EntityTier(row["tier"]),
            source=EntitySource(row["source"]),
            definition=row["definition"],
            fields=tuple(EntityField(**f) for f in json.loads(row["fields"])),
            constraints=tuple(json.loads(row["constraints"])),
            disambiguation=row["disambiguation"],
            relationships=tuple(
                EntityRelation(**r) for r in json.loads(row["relationships"])
            ),
            created_by=row["created_by"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def _entity_to_params(self, entity: EntityDefinition) -> dict:
        """Serialize an EntityDefinition into SQL parameters."""
        return {
            "name": entity.name,
            "tier": entity.tier.value,
            "source": entity.source.value,
            "definition": entity.definition,
            "fields": json.dumps(
                [f.model_dump(mode="json") for f in entity.fields],
            ),
            "constraints": json.dumps(list(entity.constraints)),
            "disambiguation": entity.disambiguation,
            "relationships": json.dumps(
                [r.model_dump(mode="json") for r in entity.relationships],
            ),
            "created_by": entity.created_by,
            "created_at": entity.created_at.isoformat(),
            "updated_at": entity.updated_at.isoformat(),
        }

    # ── CRUD ────────────────────────────────────────────────────

    async def register(self, entity: EntityDefinition) -> None:
        """Register a new entity definition."""
        db = self._require_connected()
        params = self._entity_to_params(entity)
        try:
            await db.execute(
                """INSERT INTO entity_definitions
                   (name, tier, source, definition, fields, constraints,
                    disambiguation, relationships, created_by,
                    created_at, updated_at)
                   VALUES (:name, :tier, :source, :definition, :fields,
                           :constraints, :disambiguation, :relationships,
                           :created_by, :created_at, :updated_at)""",
                params,
            )
            await db.commit()
        except sqlite3.IntegrityError as exc:
            msg = f"Entity '{entity.name}' already exists"
            raise OntologyDuplicateError(msg) from exc
        logger.info(
            ONTOLOGY_ENTITY_REGISTERED,
            entity_name=entity.name,
            tier=entity.tier.value,
        )

    async def get(self, name: str) -> EntityDefinition:
        """Retrieve an entity definition by name."""
        db = self._require_connected()
        cursor = await db.execute(
            "SELECT * FROM entity_definitions WHERE name = :name",
            {"name": name},
        )
        row = await cursor.fetchone()
        if row is None:
            msg = f"Entity '{name}' not found"
            raise OntologyNotFoundError(msg)
        return self._row_to_entity(row)

    async def update(self, entity: EntityDefinition) -> None:
        """Update an existing entity definition."""
        db = self._require_connected()
        params = self._entity_to_params(entity)
        cursor = await db.execute(
            """UPDATE entity_definitions
               SET tier = :tier, source = :source,
                   definition = :definition, fields = :fields,
                   constraints = :constraints,
                   disambiguation = :disambiguation,
                   relationships = :relationships,
                   created_by = :created_by,
                   created_at = :created_at, updated_at = :updated_at
               WHERE name = :name""",
            params,
        )
        if cursor.rowcount == 0:
            msg = f"Entity '{entity.name}' not found"
            raise OntologyNotFoundError(msg)
        await db.commit()
        logger.info(
            ONTOLOGY_ENTITY_UPDATED,
            entity_name=entity.name,
        )

    async def delete(self, name: str) -> None:
        """Delete an entity definition by name."""
        db = self._require_connected()
        cursor = await db.execute(
            "DELETE FROM entity_definitions WHERE name = :name",
            {"name": name},
        )
        if cursor.rowcount == 0:
            msg = f"Entity '{name}' not found"
            raise OntologyNotFoundError(msg)
        await db.commit()
        logger.info(ONTOLOGY_ENTITY_DELETED, entity_name=name)

    async def list_entities(
        self,
        *,
        tier: EntityTier | None = None,
    ) -> tuple[EntityDefinition, ...]:
        """List entities, optionally filtered by tier."""
        db = self._require_connected()
        if tier is not None:
            cursor = await db.execute(
                "SELECT * FROM entity_definitions WHERE tier = :tier",
                {"tier": tier.value},
            )
        else:
            cursor = await db.execute("SELECT * FROM entity_definitions")
        rows = await cursor.fetchall()
        return tuple(self._row_to_entity(row) for row in rows)

    async def search(self, query: str) -> tuple[EntityDefinition, ...]:
        """Search entities by name or definition text."""
        db = self._require_connected()
        pattern = f"%{query}%"
        cursor = await db.execute(
            """SELECT * FROM entity_definitions
               WHERE name LIKE :pattern OR definition LIKE :pattern""",
            {"pattern": pattern},
        )
        rows = await cursor.fetchall()
        logger.debug(
            ONTOLOGY_SEARCH_EXECUTED,
            query=query,
            result_count=len(rows),
        )
        return tuple(self._row_to_entity(row) for row in rows)

    async def get_version_manifest(self) -> dict[str, int]:
        """Return the latest version number for each entity."""
        db = self._require_connected()
        cursor = await db.execute(
            """SELECT entity_id, MAX(version) AS latest_version
               FROM entity_definition_versions
               GROUP BY entity_id""",
        )
        rows = await cursor.fetchall()
        return {row["entity_id"]: row["latest_version"] for row in rows}

    def get_db(self) -> aiosqlite.Connection:
        """Return the underlying database connection.

        Raises:
            OntologyConnectionError: If not connected.
        """
        return self._require_connected()
