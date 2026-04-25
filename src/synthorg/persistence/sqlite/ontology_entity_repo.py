"""SQLite-backed ontology entity repository."""

import json
import sqlite3
from collections.abc import Iterable  # noqa: TC003

import aiosqlite  # noqa: TC002

from synthorg.core.types import NotBlankStr
from synthorg.observability import get_logger
from synthorg.observability.events.ontology import (
    ONTOLOGY_ENTITY_DESERIALIZATION_FAILED,
    ONTOLOGY_ENTITY_DUPLICATE,
    ONTOLOGY_ENTITY_NOT_FOUND,
    ONTOLOGY_ENTITY_REGISTERED,
    ONTOLOGY_SEARCH_EXECUTED,
)
from synthorg.ontology.errors import (
    OntologyDuplicateError,
    OntologyError,
    OntologyNotFoundError,
)
from synthorg.ontology.models import (
    EntityDefinition,
    EntityField,
    EntityRelation,
    EntitySource,
    EntityTier,
)

logger = get_logger(__name__)


class SQLiteOntologyEntityRepository:
    """SQLite implementation of ``OntologyEntityRepository``.

    Args:
        db: Open aiosqlite connection with ``row_factory`` set.
    """

    def __init__(self, db: aiosqlite.Connection) -> None:
        self._db = db

    @property
    def backend_name(self) -> NotBlankStr:
        """Human-readable backend identifier."""
        return NotBlankStr("sqlite")

    def _row_to_entity(self, row: aiosqlite.Row) -> EntityDefinition:
        """Deserialize a database row into an EntityDefinition."""
        entity_name = row["name"]
        try:
            return EntityDefinition(
                name=entity_name,
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
        except (json.JSONDecodeError, ValueError, TypeError) as exc:
            msg = f"Corrupted entity definition for '{entity_name}'"
            logger.exception(
                ONTOLOGY_ENTITY_DESERIALIZATION_FAILED,
                entity_name=entity_name,
                error=str(exc),
            )
            raise OntologyError(msg) from exc

    def _entity_to_params(self, entity: EntityDefinition) -> dict[str, str]:
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

    async def register(self, entity: EntityDefinition) -> None:
        """Register a new entity definition."""
        params = self._entity_to_params(entity)
        try:
            await self._db.execute(
                """INSERT INTO entity_definitions
                   (name, tier, source, definition, fields, constraints,
                    disambiguation, relationships, created_by,
                    created_at, updated_at)
                   VALUES (:name, :tier, :source, :definition, :fields,
                           :constraints, :disambiguation, :relationships,
                           :created_by, :created_at, :updated_at)""",
                params,
            )
            await self._db.commit()
        except sqlite3.IntegrityError as exc:
            await self._db.rollback()
            msg = f"Entity '{entity.name}' already exists"
            logger.warning(
                ONTOLOGY_ENTITY_DUPLICATE,
                entity_name=entity.name,
                error=str(exc),
            )
            raise OntologyDuplicateError(msg) from exc
        logger.info(
            ONTOLOGY_ENTITY_REGISTERED,
            entity_name=entity.name,
            tier=entity.tier.value,
        )

    async def get(self, name: str) -> EntityDefinition:
        """Retrieve an entity definition by name."""
        cursor = await self._db.execute(
            "SELECT * FROM entity_definitions WHERE name = :name",
            {"name": name},
        )
        row = await cursor.fetchone()
        if row is None:
            msg = f"Entity '{name}' not found"
            logger.warning(ONTOLOGY_ENTITY_NOT_FOUND, entity_name=name, op="get")
            raise OntologyNotFoundError(msg)
        return self._row_to_entity(row)

    async def update(self, entity: EntityDefinition) -> None:
        """Update an existing entity definition."""
        params = self._entity_to_params(entity)
        cursor = await self._db.execute(
            """UPDATE entity_definitions
               SET tier = :tier, source = :source,
                   definition = :definition, fields = :fields,
                   constraints = :constraints,
                   disambiguation = :disambiguation,
                   relationships = :relationships,
                   updated_at = :updated_at
               WHERE name = :name""",
            params,
        )
        if cursor.rowcount == 0:
            msg = f"Entity '{entity.name}' not found"
            logger.warning(
                ONTOLOGY_ENTITY_NOT_FOUND,
                entity_name=entity.name,
                op="update",
            )
            raise OntologyNotFoundError(msg)
        await self._db.commit()

    async def delete(self, name: str) -> None:
        """Delete an entity definition by name."""
        cursor = await self._db.execute(
            "DELETE FROM entity_definitions WHERE name = :name",
            {"name": name},
        )
        if cursor.rowcount == 0:
            msg = f"Entity '{name}' not found"
            logger.warning(ONTOLOGY_ENTITY_NOT_FOUND, entity_name=name, op="delete")
            raise OntologyNotFoundError(msg)
        await self._db.commit()

    async def list_entities(
        self,
        *,
        tier: EntityTier | None = None,
    ) -> tuple[EntityDefinition, ...]:
        """List entities, optionally filtered by tier."""
        if tier is not None:
            cursor = await self._db.execute(
                """SELECT * FROM entity_definitions
                   WHERE tier = :tier LIMIT 1000""",
                {"tier": tier.value},
            )
        else:
            cursor = await self._db.execute(
                "SELECT * FROM entity_definitions LIMIT 1000",
            )
        rows = await cursor.fetchall()
        return self._rows_to_entities(rows)

    async def search(self, query: str) -> tuple[EntityDefinition, ...]:
        """Search entities by name or definition text."""
        escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{escaped}%"
        cursor = await self._db.execute(
            """SELECT * FROM entity_definitions
               WHERE name LIKE :pattern ESCAPE '\\'
                  OR definition LIKE :pattern ESCAPE '\\'
               LIMIT 1000""",
            {"pattern": pattern},
        )
        rows = list(await cursor.fetchall())
        logger.debug(
            ONTOLOGY_SEARCH_EXECUTED,
            query=query,
            result_count=len(rows),
        )
        return self._rows_to_entities(rows)

    def _rows_to_entities(
        self,
        rows: Iterable[aiosqlite.Row],
    ) -> tuple[EntityDefinition, ...]:
        """Deserialize rows, skipping corrupted entries."""
        results: list[EntityDefinition] = []
        for row in rows:
            try:
                results.append(self._row_to_entity(row))
            except OntologyError:
                continue
        return tuple(results)

    async def get_version_manifest(self) -> dict[NotBlankStr, int]:
        """Return the latest version number for each entity."""
        cursor = await self._db.execute(
            """SELECT entity_id, MAX(version) AS latest_version
               FROM entity_definition_versions
               GROUP BY entity_id""",
        )
        rows = await cursor.fetchall()
        return {NotBlankStr(row["entity_id"]): row["latest_version"] for row in rows}
