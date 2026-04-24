"""Subworkflow registry service.

A thin coordination layer on top of :class:`SubworkflowRepository`
that:

- publishes new subworkflow versions (validating ``is_subworkflow`` and
  semver uniqueness),
- resolves pinned ``(subworkflow_id, version)`` references,
- enforces deletion protection when a version is still referenced by a
  live parent workflow,
- emits observability events for every lifecycle action.

The default runtime depth limit for nested subworkflow calls is defined
here (``MAX_WORKFLOW_DEPTH``).  ``WorkflowConfig.max_subworkflow_depth``
overrides it at runtime.
"""

from typing import TYPE_CHECKING

from packaging.version import InvalidVersion, Version

from synthorg.core.types import NotBlankStr  # noqa: TC001
from synthorg.engine.errors import (
    SubworkflowIOError,
    SubworkflowNotFoundError,
)
from synthorg.observability import get_logger
from synthorg.observability.events.workflow_definition import (
    SUBWORKFLOW_DELETED,
    SUBWORKFLOW_REGISTERED,
    SUBWORKFLOW_RESOLVED,
)

if TYPE_CHECKING:
    from synthorg.engine.workflow.definition import WorkflowDefinition
    from synthorg.persistence.subworkflow_repo import (
        ParentReference,
        SubworkflowRepository,
        SubworkflowSummary,
    )

logger = get_logger(__name__)

MAX_WORKFLOW_DEPTH = 16
"""Default maximum runtime subworkflow nesting depth."""


class SubworkflowRegistry:
    """High-level service for publishing and resolving subworkflows.

    Args:
        repository: The underlying :class:`SubworkflowRepository`.
    """

    def __init__(self, repository: SubworkflowRepository) -> None:
        self._repo = repository

    async def register(self, definition: WorkflowDefinition) -> None:
        """Publish a new subworkflow version to the registry.

        Args:
            definition: The workflow definition to publish.  Must have
                ``is_subworkflow = True``.

        Raises:
            SubworkflowIOError: If ``definition`` is not marked as a
                subworkflow or carries an invalid semver.
            DuplicateRecordError: If ``(id, version)`` already exists.
        """
        if not definition.is_subworkflow:
            msg = (
                f"Cannot register workflow definition {definition.id!r} "
                "as a subworkflow: is_subworkflow flag is False"
            )
            raise SubworkflowIOError(msg)
        try:
            Version(definition.version)
        except InvalidVersion as exc:
            msg = (
                f"Subworkflow {definition.id!r} has invalid semver "
                f"{definition.version!r}: {exc}"
            )
            raise SubworkflowIOError(msg) from exc

        await self._repo.save(definition)
        logger.info(
            SUBWORKFLOW_REGISTERED,
            subworkflow_id=definition.id,
            version=definition.version,
        )

    async def get(
        self,
        subworkflow_id: NotBlankStr,
        version: NotBlankStr,
    ) -> WorkflowDefinition:
        """Resolve a pinned ``(id, version)`` reference.

        Args:
            subworkflow_id: Subworkflow identifier.
            version: Semver version string.

        Returns:
            The resolved ``WorkflowDefinition``.

        Raises:
            SubworkflowNotFoundError: If the version is not in the
                registry.
        """
        definition = await self._repo.get(subworkflow_id, version)
        if definition is None:
            msg = (
                f"Subworkflow {subworkflow_id!r} version {version!r} "
                "not found in registry"
            )
            logger.warning(
                SUBWORKFLOW_RESOLVED,
                subworkflow_id=subworkflow_id,
                version=version,
                found=False,
            )
            raise SubworkflowNotFoundError(
                msg,
                subworkflow_id=subworkflow_id,
                version=version,
            )
        logger.debug(
            SUBWORKFLOW_RESOLVED,
            subworkflow_id=subworkflow_id,
            version=version,
            found=True,
        )
        return definition

    async def list_versions(
        self,
        subworkflow_id: NotBlankStr,
    ) -> tuple[str, ...]:
        """List semver strings for a subworkflow, newest first."""
        return await self._repo.list_versions(subworkflow_id)

    async def latest_version(
        self,
        subworkflow_id: NotBlankStr,
    ) -> str | None:
        """Return the highest semver for a subworkflow, or ``None``."""
        versions = await self._repo.list_versions(subworkflow_id)
        return versions[0] if versions else None

    async def list_all(self) -> tuple[SubworkflowSummary, ...]:
        """Return summaries for every unique subworkflow in the registry."""
        return await self._repo.list_summaries()

    async def list_page(
        self,
        *,
        limit: int,
        offset: int,
    ) -> tuple[tuple[SubworkflowSummary, ...], int]:
        """Return a single page of summaries plus the authoritative total.

        Sorted by ``(name, latest_version, subworkflow_id)`` -- the
        ``subworkflow_id`` tail is required as a stable tie-breaker so
        cursor pages stay total when two subworkflows share a name +
        latest_version.

        The current implementation slices in the registry rather than
        the SQL layer because ``SubworkflowSummary.version_count``
        requires aggregating every version row per subworkflow. A true
        SQL push-down would need a window-function query plus a
        secondary fetch of the page's versions, which is a substantial
        per-backend rewrite for a list whose typical row count is
        small. Revisit if subworkflow rosters grow large enough that
        the full-fetch dominates request latency.

        Args:
            limit: Page size (rows to return).
            offset: Number of rows to skip (decoded from the cursor).

        Returns:
            ``(page, total)`` where ``page`` is the requested slice and
            ``total`` is the unique-subworkflow count.
        """
        all_summaries = await self._repo.list_summaries()
        sorted_summaries = sorted(
            all_summaries,
            key=lambda s: (s.name, s.latest_version, s.subworkflow_id),
        )
        return tuple(sorted_summaries[offset : offset + limit]), len(sorted_summaries)

    async def search(
        self,
        query: NotBlankStr,
    ) -> tuple[SubworkflowSummary, ...]:
        """Search subworkflows by name or description substring."""
        return await self._repo.search(query)

    async def delete(
        self,
        subworkflow_id: NotBlankStr,
        version: NotBlankStr,
    ) -> None:
        """Delete a subworkflow version with parent-reference protection.

        Uses an atomic check-and-delete to eliminate the TOCTOU race
        between the parent scan and the actual deletion.

        Raises:
            SubworkflowIOError: If any live parent still pins this
                ``(id, version)`` coordinate.
            SubworkflowNotFoundError: If the coordinate does not exist.
        """
        deleted, parents = await self._repo.delete_if_unreferenced(
            subworkflow_id,
            version,
        )
        if parents:
            names = ", ".join(f"{p.parent_name!r}" for p in parents)
            msg = (
                f"Cannot delete subworkflow {subworkflow_id!r} version "
                f"{version!r}: still referenced by {len(parents)} parent "
                f"workflow(s): {names}"
            )
            logger.warning(
                SUBWORKFLOW_DELETED,
                subworkflow_id=subworkflow_id,
                version=version,
                deleted=False,
                blocked_by_parents=len(parents),
            )
            raise SubworkflowIOError(msg)

        if not deleted:
            msg = (
                f"Subworkflow {subworkflow_id!r} version {version!r} "
                "not found in registry"
            )
            logger.warning(
                SUBWORKFLOW_DELETED,
                subworkflow_id=subworkflow_id,
                version=version,
                deleted=False,
                reason="not_found",
            )
            raise SubworkflowNotFoundError(
                msg,
                subworkflow_id=subworkflow_id,
                version=version,
            )
        logger.info(
            SUBWORKFLOW_DELETED,
            subworkflow_id=subworkflow_id,
            version=version,
        )

    async def find_parents(
        self,
        subworkflow_id: NotBlankStr,
        version: NotBlankStr | None = None,
    ) -> tuple[ParentReference, ...]:
        """Return parent workflow definitions referencing a subworkflow."""
        return await self._repo.find_parents(subworkflow_id, version)
