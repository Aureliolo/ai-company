"""Workflow definition service layer.

Wraps :class:`WorkflowDefinitionRepository` +
:class:`VersionRepository[WorkflowDefinition]` so the ``/workflows``
controller does not touch ``app_state.persistence.*`` directly. Handles
the cascade from definition deletion to its version snapshots in one
place so the audit trail stays consistent.
"""

from typing import TYPE_CHECKING

from synthorg.core.enums import WorkflowType  # noqa: TC001
from synthorg.core.types import NotBlankStr  # noqa: TC001
from synthorg.engine.workflow.definition import WorkflowDefinition  # noqa: TC001
from synthorg.observability import get_logger
from synthorg.observability.events.workflow_definition import (
    WORKFLOW_DEF_CREATED,
    WORKFLOW_DEF_DELETED,
    WORKFLOW_DEF_UPDATED,
)
from synthorg.observability.events.workflow_version import (
    WORKFLOW_VERSION_SNAPSHOT_FAILED,
)

if TYPE_CHECKING:
    from synthorg.persistence.version_repo import VersionRepository
    from synthorg.persistence.workflow_definition_repo import (
        WorkflowDefinitionRepository,
    )

logger = get_logger(__name__)


class WorkflowService:
    """Service for workflow definition CRUD + version cascade."""

    __slots__ = ("_definitions", "_versions")

    def __init__(
        self,
        *,
        definition_repo: WorkflowDefinitionRepository,
        version_repo: VersionRepository[WorkflowDefinition],
    ) -> None:
        self._definitions = definition_repo
        self._versions = version_repo

    async def list_definitions(
        self,
        *,
        workflow_type: WorkflowType | None = None,
    ) -> tuple[WorkflowDefinition, ...]:
        """List definitions filtered by optional workflow type."""
        return await self._definitions.list_definitions(
            workflow_type=workflow_type,
        )

    async def get_definition(
        self,
        definition_id: NotBlankStr,
    ) -> WorkflowDefinition | None:
        """Fetch a single definition by id."""
        return await self._definitions.get(definition_id)

    async def create_definition(
        self,
        definition: WorkflowDefinition,
    ) -> WorkflowDefinition:
        """Persist a new definition with audit log."""
        await self._definitions.save(definition)
        logger.info(WORKFLOW_DEF_CREATED, definition_id=definition.id)
        return definition

    async def update_definition(
        self,
        definition: WorkflowDefinition,
    ) -> WorkflowDefinition:
        """Upsert an existing definition with audit log."""
        await self._definitions.save(definition)
        logger.info(WORKFLOW_DEF_UPDATED, definition_id=definition.id)
        return definition

    async def delete_definition(
        self,
        definition_id: NotBlankStr,
    ) -> bool:
        """Delete a definition and its version snapshots.

        Returns ``True`` when the definition row was removed, ``False``
        when no row matched. The version-snapshot cleanup is best-effort:
        a failure there is logged with
        :data:`WORKFLOW_VERSION_SNAPSHOT_FAILED` but does not block the
        overall delete (orphaned snapshots are tolerable and
        periodically swept).
        """
        deleted = await self._definitions.delete(definition_id)
        if not deleted:
            return False

        try:
            await self._versions.delete_versions_for_entity(definition_id)
        except Exception as exc:
            logger.warning(
                WORKFLOW_VERSION_SNAPSHOT_FAILED,
                definition_id=definition_id,
                error_type=type(exc).__name__,
                stage="cascade_delete",
            )

        logger.info(WORKFLOW_DEF_DELETED, definition_id=definition_id)
        return True
