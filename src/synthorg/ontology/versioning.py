"""Versioning integration for the ontology subsystem.

Provides a factory to create a ``VersioningService[EntityDefinition]``
from the ontology backend's database connection.
"""

import json
from typing import TYPE_CHECKING

from synthorg.ontology.models import EntityDefinition
from synthorg.persistence.sqlite.version_repo import SQLiteVersionRepository
from synthorg.versioning.service import VersioningService

if TYPE_CHECKING:
    import aiosqlite


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
        deserialize_snapshot=EntityDefinition.model_validate_json,
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
