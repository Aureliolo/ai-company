"""Subworkflow service layer.

Wraps :class:`SubworkflowRegistry` with the business logic the MCP
write facade needs: paginated listing, version-pinning helpers,
parent-cascade protection on delete, and audit-event emission for
each lifecycle step. Controllers and MCP handlers route through this
service so persistence access stays behind a single facade.

The thin :class:`SubworkflowRegistry` underneath is preserved for the
pure resolution paths (engine activation, blueprint loaders) that
already depend on its narrow surface; this service is the broader
"control plane" entry point.
"""

from typing import TYPE_CHECKING

from synthorg.core.types import NotBlankStr
from synthorg.engine.errors import (
    SubworkflowIOError,
    SubworkflowNotFoundError,
)
from synthorg.observability import get_logger
from synthorg.observability.events.workflow_definition import (
    SUBWORKFLOW_DELETED,
    SUBWORKFLOW_REGISTERED,
)

if TYPE_CHECKING:
    from synthorg.engine.workflow.definition import WorkflowDefinition
    from synthorg.engine.workflow.subworkflow_registry import SubworkflowRegistry
    from synthorg.persistence.subworkflow_repo import (
        ParentReference,
        SubworkflowSummary,
    )
    from synthorg.persistence.workflow_definition_repo import (
        WorkflowDefinitionRepository,
    )

logger = get_logger(__name__)


class SubworkflowHasParentsError(SubworkflowIOError):
    """Raised when ``delete`` is blocked by live parent references.

    Carries the parent list so callers can surface the conflict to the
    operator without re-querying.
    """

    def __init__(
        self,
        message: str,
        *,
        subworkflow_id: str,
        version: str,
        parents: tuple[ParentReference, ...],
    ) -> None:
        if not parents:
            msg = (
                "SubworkflowHasParentsError requires at least one parent "
                "reference; raise SubworkflowNotFoundError instead when "
                "the subworkflow has no live parents."
            )
            raise ValueError(msg)
        super().__init__(message)
        self.subworkflow_id = subworkflow_id
        self.version = version
        self.parents = parents


class SubworkflowService:
    """Control-plane service for subworkflows.

    Adds a paginated list with optional substring search, version-pinning
    resolution (``version=None`` resolves to latest), parent-cascade
    enforcement before delete, and audit-log emission on publish + delete.
    Existing engine paths (activation, blueprint loading) keep using
    :class:`SubworkflowRegistry` directly for low-level resolution.
    """

    __slots__ = ("_definition_repo", "_registry")

    def __init__(
        self,
        *,
        registry: SubworkflowRegistry,
        definition_repo: WorkflowDefinitionRepository,
    ) -> None:
        self._registry = registry
        self._definition_repo = definition_repo

    async def list_summaries(
        self,
        *,
        offset: int,
        limit: int,
        query: str | None = None,
    ) -> tuple[tuple[SubworkflowSummary, ...], int]:
        """Return a paginated list of subworkflow summaries.

        When ``query`` is provided, the registry's substring search
        runs first; otherwise we fall back to the unfiltered summary
        list. Results are sorted by ``(name, latest_version,
        subworkflow_id)`` and offset/limit are applied here so callers
        get a stable total count.
        """
        if offset < 0:
            msg = f"offset must be >= 0, got {offset}"
            raise ValueError(msg)
        if limit < 1:
            msg = f"limit must be >= 1, got {limit}"
            raise ValueError(msg)

        if query is not None and query.strip():
            summaries = await self._registry.search(NotBlankStr(query.strip()))
        else:
            summaries = await self._registry.list_all()
        sorted_summaries = sorted(
            summaries,
            key=lambda s: (s.name, s.latest_version, s.subworkflow_id),
        )
        total = len(sorted_summaries)
        page = tuple(sorted_summaries[offset : offset + limit])
        return page, total

    async def get(
        self,
        subworkflow_id: NotBlankStr,
        version: NotBlankStr | None = None,
    ) -> WorkflowDefinition:
        """Resolve a subworkflow definition.

        When ``version`` is omitted, the latest semver is selected. A
        missing subworkflow raises :class:`SubworkflowNotFoundError`.
        """
        if version is None:
            latest = await self._registry.latest_version(subworkflow_id)
            if latest is None:
                msg = f"Subworkflow {subworkflow_id!r} has no versions in the registry"
                raise SubworkflowNotFoundError(
                    msg,
                    subworkflow_id=str(subworkflow_id),
                    version="<latest>",
                )
            return await self._registry.get(subworkflow_id, NotBlankStr(latest))
        return await self._registry.get(subworkflow_id, version)

    async def create(
        self,
        definition: WorkflowDefinition,
        *,
        saved_by: str,
    ) -> WorkflowDefinition:
        """Publish a new subworkflow version.

        Validates that ``is_subworkflow=True``, delegates to the
        registry for the atomic write, and emits the publish audit
        event including the actor.
        """
        if not definition.is_subworkflow:
            msg = (
                f"Cannot create subworkflow from definition {definition.id!r}: "
                "is_subworkflow flag is False"
            )
            raise SubworkflowIOError(msg)
        await self._registry.register(definition)
        logger.info(
            SUBWORKFLOW_REGISTERED,
            subworkflow_id=definition.id,
            version=definition.version,
            saved_by=saved_by,
            stage="service.create",
        )
        return definition

    async def delete(
        self,
        subworkflow_id: NotBlankStr,
        version: NotBlankStr,
        *,
        reason: str,
        actor_id: str,
    ) -> None:
        """Delete a subworkflow version after parent-cascade check.

        The check-then-delete sequence is intentionally non-atomic at
        the service layer: ``find_parents`` here is for early,
        operator-friendly error reporting only. The actual safety net
        is :meth:`SubworkflowRegistry.delete`, which delegates to the
        repository's atomic ``delete_if_unreferenced``. A parent that
        appears in the narrow TOCTOU window between this check and the
        registry call still gets caught at the SQL level and surfaces
        as a `SubworkflowIOError`.

        Raises:
            SubworkflowHasParentsError: If any live parent workflow
                still pins ``(subworkflow_id, version)``. The exception
                carries the parent list so callers can surface the
                conflict without a second query.
            SubworkflowNotFoundError: If the coordinate does not exist.
        """
        parents = await self._registry.find_parents(subworkflow_id, version)
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
                actor_id=actor_id,
                reason=reason,
            )
            raise SubworkflowHasParentsError(
                msg,
                subworkflow_id=str(subworkflow_id),
                version=str(version),
                parents=parents,
            )
        await self._registry.delete(subworkflow_id, version)
        logger.info(
            SUBWORKFLOW_DELETED,
            subworkflow_id=subworkflow_id,
            version=version,
            actor_id=actor_id,
            reason=reason,
            stage="service.delete",
        )


__all__ = [
    "SubworkflowHasParentsError",
    "SubworkflowService",
]
