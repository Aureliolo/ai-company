"""Repository protocol for workflow definition persistence."""

from typing import Protocol, runtime_checkable

from synthorg.core.enums import WorkflowType  # noqa: TC001
from synthorg.core.types import NotBlankStr  # noqa: TC001
from synthorg.engine.workflow.definition import WorkflowDefinition  # noqa: TC001


@runtime_checkable
class WorkflowDefinitionRepository(Protocol):
    """CRUD interface for workflow definition persistence.

    Workflow definitions are design-time blueprints for visual
    workflow graphs, stored with their full node/edge data.
    """

    async def save(self, definition: WorkflowDefinition) -> None:
        """Persist a workflow definition (insert or update).

        Args:
            definition: The workflow definition to persist.

        Raises:
            PersistenceError: If the operation fails.
        """
        ...

    async def get(self, definition_id: NotBlankStr) -> WorkflowDefinition | None:
        """Retrieve a workflow definition by its ID.

        Args:
            definition_id: The definition identifier.

        Returns:
            The definition, or ``None`` if not found.

        Raises:
            PersistenceError: If the operation fails.
        """
        ...

    async def list_definitions(
        self,
        *,
        workflow_type: WorkflowType | None = None,
    ) -> tuple[WorkflowDefinition, ...]:
        """List workflow definitions with optional filters.

        Args:
            workflow_type: Filter by workflow type.

        Returns:
            Matching definitions as a tuple.

        Raises:
            PersistenceError: If the operation fails.
        """
        ...

    async def delete(self, definition_id: NotBlankStr) -> bool:
        """Delete a workflow definition by ID.

        Args:
            definition_id: The definition identifier.

        Returns:
            ``True`` if the definition was deleted, ``False`` if not found.

        Raises:
            PersistenceError: If the operation fails.
        """
        ...
