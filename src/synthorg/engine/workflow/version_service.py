"""Workflow version service layer.

Wraps the generic :class:`VersionRepository` for workflow definitions
behind a domain-specific facade. The MCP write surface and any future
controller route through this service so the persistence boundary stays
honored (handlers never reach into ``app_state.persistence`` directly).
"""

from typing import TYPE_CHECKING

from synthorg.core.types import NotBlankStr  # noqa: TC001 -- runtime annotation
from synthorg.observability import get_logger
from synthorg.observability.events.workflow_version import (
    WORKFLOW_VERSION_INVALID_REQUEST,
)

if TYPE_CHECKING:
    from synthorg.engine.workflow.definition import WorkflowDefinition
    from synthorg.persistence.version_repo import VersionRepository
    from synthorg.versioning.models import VersionSnapshot

logger = get_logger(__name__)


class WorkflowVersionService:
    """Read-side facade over workflow definition version snapshots."""

    __slots__ = ("_repo",)

    def __init__(
        self,
        *,
        version_repo: VersionRepository[WorkflowDefinition],
    ) -> None:
        self._repo = version_repo

    async def list_versions(
        self,
        definition_id: NotBlankStr,
        *,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[tuple[VersionSnapshot[WorkflowDefinition], ...], int]:
        """Return a paginated list of version snapshots and the total count.

        Snapshots are returned newest-first, matching the underlying
        repository's ordering. The total is queried via
        ``count_versions`` so paginated callers can drive a UI without
        a second round trip.
        """
        if offset < 0:
            logger.warning(
                WORKFLOW_VERSION_INVALID_REQUEST,
                definition_id=str(definition_id),
                param="offset",
                value=offset,
            )
            msg = f"offset must be >= 0, got {offset}"
            raise ValueError(msg)
        if limit < 1:
            logger.warning(
                WORKFLOW_VERSION_INVALID_REQUEST,
                definition_id=str(definition_id),
                param="limit",
                value=limit,
            )
            msg = f"limit must be >= 1, got {limit}"
            raise ValueError(msg)
        total = await self._repo.count_versions(definition_id)
        page = await self._repo.list_versions(
            definition_id,
            limit=limit,
            offset=offset,
        )
        return page, total

    async def get_version(
        self,
        definition_id: NotBlankStr,
        revision: int,
    ) -> VersionSnapshot[WorkflowDefinition] | None:
        """Return a specific version snapshot, or ``None`` if absent."""
        if revision < 1:
            logger.warning(
                WORKFLOW_VERSION_INVALID_REQUEST,
                definition_id=str(definition_id),
                param="revision",
                value=revision,
            )
            msg = f"revision must be >= 1, got {revision}"
            raise ValueError(msg)
        return await self._repo.get_version(definition_id, revision)


__all__ = ["WorkflowVersionService"]
