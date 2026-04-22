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
from synthorg.persistence.errors import VersionConflictError

if TYPE_CHECKING:
    from synthorg.persistence.version_repo import VersionRepository
    from synthorg.persistence.workflow_definition_repo import (
        WorkflowDefinitionRepository,
    )
    from synthorg.versioning.service import VersioningService

logger = get_logger(__name__)


class WorkflowDefinitionExistsError(Exception):
    """Raised when ``create_definition`` targets an id that already exists."""


class WorkflowDefinitionNotFoundError(Exception):
    """Raised when ``fetch_for_update`` / update targets a missing id."""


class WorkflowDefinitionRevisionMismatchError(Exception):
    """Raised when an optimistic-concurrency revision check fails.

    ``actual`` is ``None`` when the persistence layer surfaces a
    conflict without a usable stored-revision read (e.g. the follow-up
    lookup raced with a delete). Callers should treat ``None`` as
    "unknown stored revision" rather than a sentinel integer.
    """

    def __init__(
        self,
        message: str,
        *,
        definition_id: str,
        expected: int,
        actual: int | None,
    ) -> None:
        super().__init__(message)
        self.definition_id = definition_id
        self.expected = expected
        self.actual = actual


class WorkflowService:
    """Service for workflow definition CRUD + version cascade.

    When ``versioning_service`` is provided, :meth:`create_definition`
    and :meth:`update_definition` persist the definition AND best-effort
    snapshot the new revision in a single service call so controllers
    no longer need to reach into ``VersioningService`` directly. A
    snapshot failure does not fail the whole operation (orphaned
    versions are tolerable and periodically swept); it is logged at
    WARNING so operators can investigate without losing the definition
    write.
    """

    __slots__ = ("_definitions", "_versioning", "_versions")

    def __init__(
        self,
        *,
        definition_repo: WorkflowDefinitionRepository,
        version_repo: VersionRepository[WorkflowDefinition],
        versioning_service: VersioningService[WorkflowDefinition] | None = None,
    ) -> None:
        self._definitions = definition_repo
        self._versions = version_repo
        self._versioning = versioning_service

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
        *,
        saved_by: str | None = None,
    ) -> WorkflowDefinition:
        """Persist a new definition with audit log.

        Uses the repository's atomic ``create_if_absent`` so two
        concurrent callers with the same ``definition.id`` cannot both
        observe "not found" and then both upsert via ``save`` -- that
        check-then-save pattern has a TOCTOU window the backend's
        ``INSERT ... ON CONFLICT DO NOTHING`` closes at the SQL level.

        When ``saved_by`` is provided AND the service was constructed
        with a ``VersioningService``, a best-effort version snapshot is
        recorded for the new revision. Snapshot failures are logged at
        WARNING and swallowed; the definition write is authoritative.

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
        await self._best_effort_snapshot(definition, saved_by)
        logger.info(WORKFLOW_DEF_CREATED, definition_id=definition.id)
        return definition

    async def update_definition(
        self,
        definition: WorkflowDefinition,
        *,
        saved_by: str | None = None,
    ) -> WorkflowDefinition:
        """Update an existing definition with audit log.

        Uses the repository's ``update_if_exists`` so a row deleted
        after the controller's existence check cannot be silently
        resurrected by an upsert while still emitting
        ``WORKFLOW_DEF_UPDATED``. A missing row now surfaces as
        ``WorkflowDefinitionNotFoundError`` (HTTP 404) -- create/update
        audit semantics stay distinct even under delete races.

        When ``saved_by`` is provided AND the service was constructed
        with a ``VersioningService``, a best-effort version snapshot
        is recorded. Same best-effort semantics as
        :meth:`create_definition`.

        Raises:
            WorkflowDefinitionNotFoundError: No row exists for
                ``definition.id`` -- caller should use
                ``create_definition``.
            WorkflowDefinitionRevisionMismatchError: A row exists but
                its stored ``revision`` does not match
                ``definition.revision - 1`` (optimistic-concurrency
                failure). Translated from the persistence layer's
                ``VersionConflictError`` so callers of this service
                never depend on a persistence-level exception type.
        """
        try:
            updated = await self._definitions.update_if_exists(definition)
        except VersionConflictError as exc:
            # Look up the stored revision so the domain exception reports
            # the real ``actual`` value rather than a made-up sentinel.
            # If the follow-up read itself fails, fall back to ``None``
            # for ``actual`` and let the domain exception carry just the
            # expected revision; swallowing that lookup is fine because
            # we still propagate the original conflict as ``__cause__``.
            stored_revision: int | None = None
            try:
                existing = await self._definitions.get(definition.id)
            except MemoryError, RecursionError:
                # Fatal system errors must propagate even from a
                # best-effort probe; otherwise the outer ``raise`` below
                # would swallow them.
                raise
            except Exception as lookup_exc:
                logger.debug(
                    WORKFLOW_DEF_VERSION_CONFLICT,
                    definition_id=str(definition.id),
                    stage="stored_revision_lookup_failed",
                    error_type=type(lookup_exc).__name__,
                )
            else:
                if existing is not None:
                    stored_revision = existing.revision
            logger.warning(
                WORKFLOW_DEF_VERSION_CONFLICT,
                definition_id=str(definition.id),
                operation="update_definition",
                expected_revision=definition.revision,
                stored_revision=stored_revision,
            )
            msg = (
                f"Workflow definition {definition.id!r} revision conflict:"
                f" expected {definition.revision},"
                f" stored {stored_revision}"
            )
            raise WorkflowDefinitionRevisionMismatchError(
                msg,
                definition_id=str(definition.id),
                expected=definition.revision,
                actual=stored_revision,
            ) from exc
        if not updated:
            logger.warning(
                WORKFLOW_DEF_NOT_FOUND,
                definition_id=str(definition.id),
                operation="update_definition",
            )
            msg = (
                f"Workflow definition {definition.id!r} not found; "
                "use create_definition to insert it"
            )
            raise WorkflowDefinitionNotFoundError(msg)
        await self._best_effort_snapshot(definition, saved_by)
        logger.info(WORKFLOW_DEF_UPDATED, definition_id=definition.id)
        return definition

    async def _best_effort_snapshot(
        self,
        definition: WorkflowDefinition,
        saved_by: str | None,
    ) -> None:
        """Record a version snapshot if the service has versioning wired in.

        No-op when either the versioning service is not attached or the
        caller did not provide ``saved_by`` (e.g. system-driven writes
        that do not attribute authorship). Snapshot failures are logged
        at WARNING and swallowed -- orphaned snapshots are tolerable and
        periodically swept; losing a definition write because the
        snapshot table is momentarily unavailable is not.
        """
        if self._versioning is None or saved_by is None:
            return
        try:
            await self._versioning.snapshot_if_changed(
                entity_id=definition.id,
                snapshot=definition,
                saved_by=saved_by,
            )
        except MemoryError, RecursionError:
            # Fatal system errors must propagate so the workload can
            # shed load; best-effort logging is the wrong response here.
            raise
        except Exception as exc:
            logger.warning(
                WORKFLOW_VERSION_SNAPSHOT_FAILED,
                definition_id=definition.id,
                revision=definition.revision,
                error_type=type(exc).__name__,
                error=safe_error_description(exc),
            )

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
        except MemoryError, RecursionError:
            raise
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
