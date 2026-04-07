"""Generic versioning service.

Wraps a :class:`~synthorg.persistence.version_repo.VersionRepository`
to provide content-addressable snapshot creation: a new version is only
persisted when the entity content has actually changed.
"""

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel

from synthorg.observability import get_logger
from synthorg.observability.events.versioning import (
    VERSION_SAVED,
    VERSION_SNAPSHOT_SKIPPED,
)
from synthorg.versioning.hashing import compute_content_hash
from synthorg.versioning.models import VersionSnapshot

if TYPE_CHECKING:
    from synthorg.persistence.version_repo import VersionRepository

logger = get_logger(__name__)


class VersioningService[T: BaseModel]:
    """Content-aware versioning service for Pydantic model entities.

    A new :class:`~synthorg.versioning.models.VersionSnapshot` is
    persisted only when the entity content has changed (determined by
    comparing SHA-256 content hashes).  Identical content produces a
    no-op, avoiding version inflation from spurious no-change saves.

    The version number is computed as ``latest.version + 1`` (or 1 if
    no versions exist).  The repository uses ``INSERT OR IGNORE``
    semantics, so concurrent saves of the same version number are safe:
    the second write is silently dropped.  This trade-off is acceptable
    because identity-like entities are updated at low frequency.

    Args:
        repo: Repository managing the entity's version snapshots.
    """

    def __init__(self, repo: VersionRepository[T]) -> None:
        self._repo = repo

    async def snapshot_if_changed(
        self,
        entity_id: str,
        snapshot: T,
        saved_by: str,
    ) -> VersionSnapshot[T] | None:
        """Persist a new version only when content has changed.

        Computes the SHA-256 hash of the snapshot, fetches the latest
        persisted version, and skips persistence when the hashes match.

        Args:
            entity_id: String primary key of the entity being versioned.
            snapshot: The current entity state to snapshot.
            saved_by: Identifier of the actor triggering the snapshot.

        Returns:
            The newly created :class:`VersionSnapshot` if content
            changed, or ``None`` if content was unchanged.

        Raises:
            PersistenceError: If the repository operation fails.
        """
        content_hash = compute_content_hash(snapshot)
        latest = await self._repo.get_latest_version(entity_id)

        if latest is not None and latest.content_hash == content_hash:
            logger.debug(
                VERSION_SNAPSHOT_SKIPPED,
                entity_id=entity_id,
                content_hash=content_hash,
                current_version=latest.version,
            )
            return None

        new_version_num = (latest.version + 1) if latest is not None else 1
        version = VersionSnapshot(
            entity_id=entity_id,
            version=new_version_num,
            content_hash=content_hash,
            snapshot=snapshot,
            saved_by=saved_by,
            saved_at=datetime.now(UTC),
        )
        inserted = await self._repo.save_version(version)
        if not inserted:
            # A concurrent writer beat us to this (entity_id, version) pair.
            # Return the version that was actually persisted rather than the
            # one we constructed, so the caller always sees a live snapshot.
            return await self._repo.get_latest_version(entity_id)
        logger.info(
            VERSION_SAVED,
            entity_id=entity_id,
            version=new_version_num,
            saved_by=saved_by,
        )
        return version

    async def get_latest(
        self,
        entity_id: str,
    ) -> VersionSnapshot[T] | None:
        """Retrieve the most recent version snapshot for an entity.

        Convenience delegating to the underlying repository.

        Args:
            entity_id: String primary key of the entity.

        Returns:
            The latest :class:`VersionSnapshot`, or ``None`` if none exist.

        Raises:
            PersistenceError: If the repository operation fails.
        """
        return await self._repo.get_latest_version(entity_id)
