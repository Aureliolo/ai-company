"""Versioning integration for the ontology subsystem.

Provides a factory to create a ``VersioningService[EntityDefinition]``
from the ontology backend's database connection.
"""

import json
from typing import TYPE_CHECKING

from pydantic import ValidationError

from synthorg.observability import get_logger
from synthorg.ontology.errors import OntologyError
from synthorg.ontology.models import EntityDefinition
from synthorg.persistence.sqlite.version_repo import SQLiteVersionRepository
from synthorg.versioning.service import VersioningService

if TYPE_CHECKING:
    import aiosqlite

logger = get_logger(__name__)


def _safe_deserialize_snapshot(raw: str) -> EntityDefinition:
    """Deserialize a JSON snapshot, wrapping validation errors."""
    try:
        return EntityDefinition.model_validate_json(raw)
    except ValidationError as exc:
        msg = "Corrupted entity definition version snapshot"
        logger.warning(msg, error=str(exc))
        raise OntologyError(msg) from exc


def create_ontology_version_repo(
    db: aiosqlite.Connection,
) -> SQLiteVersionRepository[EntityDefinition]:
    """Create a SQLiteVersionRepository for EntityDefinition.

    Args:
        db: An open aiosqlite connection (the ontology backend's).

    Returns:
        A repository targeting the ``entity_definition_versions`` table.
    """
    return SQLiteVersionRepository(
        db,
        table_name="entity_definition_versions",
        serialize_snapshot=lambda m: json.dumps(
            m.model_dump(mode="json"),
        ),
        deserialize_snapshot=_safe_deserialize_snapshot,
    )


def create_ontology_versioning(
    db: aiosqlite.Connection,
) -> VersioningService[EntityDefinition]:
    """Create a VersioningService for EntityDefinition.

    Convenience that composes ``create_ontology_version_repo`` with
    ``VersioningService``.

    Args:
        db: An open aiosqlite connection.

    Returns:
        A versioning service for entity definitions.
    """
    repo = create_ontology_version_repo(db)
    return VersioningService(repo)
