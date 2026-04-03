"""In-memory fake workflow definition repository for API unit tests."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from synthorg.core.enums import WorkflowType
    from synthorg.engine.workflow.definition import WorkflowDefinition


class FakeWorkflowDefinitionRepository:
    """In-memory workflow definition repository for tests."""

    def __init__(self) -> None:
        self._definitions: dict[str, WorkflowDefinition] = {}

    async def save(self, definition: WorkflowDefinition) -> None:
        self._definitions[definition.id] = definition

    async def get(self, definition_id: str) -> WorkflowDefinition | None:
        return self._definitions.get(definition_id)

    async def list_definitions(
        self,
        *,
        workflow_type: WorkflowType | None = None,
    ) -> tuple[WorkflowDefinition, ...]:
        result = list(self._definitions.values())
        if workflow_type is not None:
            result = [d for d in result if d.workflow_type == workflow_type]
        return tuple(result)

    async def delete(self, definition_id: str) -> bool:
        return self._definitions.pop(definition_id, None) is not None
