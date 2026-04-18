"""Versioning integration for the ontology subsystem.

Provides a factory that composes ``VersioningService[EntityDefinition]``
on top of the persistence layer's ``SQLiteVersionRepository``.  After
A5 consolidation the DB handle is sourced from the shared
:class:`PersistenceBackend` rather than a standalone ontology backend.
"""

import json
from typing import Any

from pydantic import ValidationError

from synthorg.observability import get_logger
from synthorg.ontology.errors import OntologyError
from synthorg.ontology.models import EntityDefinition
from synthorg.persistence.sqlite.version_repo import SQLiteVersionRepository
from synthorg.versioning.service import VersioningService

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
    db: Any,
) -> SQLiteVersionRepository[EntityDefinition]:
    """Create a SQLiteVersionRepository for EntityDefinition.

    Args:
        db: An open aiosqlite connection produced by the persistence
            backend.  Accepted as ``Any`` because importing
            ``aiosqlite`` outside ``persistence/`` would violate the
            boundary linter; the actual handle is passed straight
            through to the repository.

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
    db: Any,
) -> VersioningService[EntityDefinition]:
    """Create a VersioningService for EntityDefinition.

    Args:
        db: An open aiosqlite connection (see above note on the type).

    Returns:
        A versioning service for entity definitions.
    """
    repo = create_ontology_version_repo(db)
    return VersioningService(repo)
