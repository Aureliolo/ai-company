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
from synthorg.observability import get_logger, safe_error_description
from synthorg.observability.events.workflow_definition import (
    WORKFLOW_DEF_CREATE_CONFLICT,
    WORKFLOW_DEF_CREATED,
    WORKFLOW_DEF_DELETED,
    WORKFLOW_DEF_NOT_FOUND,
    WORKFLOW_DEF_UPDATED,
    WORKFLOW_DEF_VERSION_CONFLICT,
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


class WorkflowDefinitionExistsError(Exception):
    """Raised when ``create_definition`` targets an id that already exists."""


class WorkflowDefinitionNotFoundError(Exception):
    """Raised when ``fetch_for_update`` / update targets a missing id."""


class WorkflowDefinitionRevisionMismatchError(Exception):
    """Raised when an optimistic-concurrency revision check fails."""

    def __init__(
        self,
        message: str,
        *,
        definition_id: str,
        expected: int,
        actual: int,
    ) -> None:
        super().__init__(message)
        self.definition_id = definition_id
        self.expected = expected
        self.actual = actual


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

    async def fetch_for_update(
        self,
        definition_id: NotBlankStr,
        expected_revision: int | None,
    ) -> WorkflowDefinition:
        """Return the definition for an optimistic-concurrency update.

        Enforces the same preconditions the controller previously ran
        inline against the repository so all persistence access flows
        through the service layer:

        * the definition exists;
        * when *expected_revision* is supplied, the stored revision
          matches it.

        Raises:
            WorkflowDefinitionNotFoundError: The id does not exist.
            WorkflowDefinitionRevisionMismatchError: The stored revision
                differs from *expected_revision*.
        """
        existing = await self._definitions.get(definition_id)
        if existing is None:
            logger.warning(
                WORKFLOW_DEF_NOT_FOUND,
                definition_id=str(definition_id),
                operation="fetch_for_update",
            )
            msg = f"Workflow definition {definition_id!r} not found"
            raise WorkflowDefinitionNotFoundError(msg)
        if expected_revision is not None and expected_revision != existing.revision:
            logger.warning(
                WORKFLOW_DEF_VERSION_CONFLICT,
                definition_id=str(definition_id),
                expected_revision=expected_revision,
                stored_revision=existing.revision,
            )
            msg = (
                f"Workflow definition {definition_id!r} revision conflict: "
                f"expected {expected_revision}, stored {existing.revision}"
            )
            raise WorkflowDefinitionRevisionMismatchError(
                msg,
                definition_id=str(definition_id),
                expected=expected_revision,
                actual=existing.revision,
            )
        return existing

    async def create_definition(
        self,
        definition: WorkflowDefinition,
    ) -> WorkflowDefinition:
        """Persist a new definition with audit log.

        Uses the repository's atomic ``create_if_absent`` so two
        concurrent callers with the same ``definition.id`` cannot both
        observe "not found" and then both upsert via ``save`` -- that
        check-then-save pattern has a TOCTOU window the backend's
        ``INSERT ... ON CONFLICT DO NOTHING`` closes at the SQL level.

        Raises:
            WorkflowDefinitionExistsError: ``definition.id`` already
                exists -- caller should use ``update_definition``.
        """
        inserted = await self._definitions.create_if_absent(definition)
        if not inserted:
            logger.warning(
                WORKFLOW_DEF_CREATE_CONFLICT,
                definition_id=str(definition.id),
                reason="duplicate_id",
            )
            msg = (
                f"Workflow definition {definition.id!r} already exists; "
                "use update_definition to modify it"
            )
            raise WorkflowDefinitionExistsError(msg)
        logger.info(WORKFLOW_DEF_CREATED, definition_id=definition.id)
        return definition

    async def update_definition(
        self,
        definition: WorkflowDefinition,
    ) -> WorkflowDefinition:
        """Upsert an existing definition with audit log.

        Intentionally does NOT pre-check existence so optimistic
        concurrency retries (create-or-update from the controller's
        ``fetch_existing_for_update`` flow) continue to work without
        an extra round-trip; the controller already checks existence
        before invoking ``update``.
        """
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
                error=safe_error_description(exc),
                stage="cascade_delete",
            )

        logger.info(WORKFLOW_DEF_DELETED, definition_id=definition_id)
        return True
