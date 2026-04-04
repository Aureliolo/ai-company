"""In-memory fake workflow repositories for API unit tests."""

import copy
from typing import TYPE_CHECKING

from synthorg.core.enums import WorkflowExecutionStatus
from synthorg.persistence.errors import DuplicateRecordError, VersionConflictError

if TYPE_CHECKING:
    from synthorg.core.enums import WorkflowType
    from synthorg.engine.workflow.definition import WorkflowDefinition
    from synthorg.engine.workflow.execution_models import WorkflowExecution
    from synthorg.engine.workflow.version import WorkflowDefinitionVersion


class FakeWorkflowDefinitionRepository:
    """In-memory workflow definition repository for tests."""

    def __init__(self) -> None:
        self._definitions: dict[str, WorkflowDefinition] = {}

    async def save(self, definition: WorkflowDefinition) -> None:
        self._definitions[definition.id] = copy.deepcopy(definition)

    async def get(self, definition_id: str) -> WorkflowDefinition | None:
        stored = self._definitions.get(definition_id)
        return copy.deepcopy(stored) if stored is not None else None

    async def list_definitions(
        self,
        *,
        workflow_type: WorkflowType | None = None,
    ) -> tuple[WorkflowDefinition, ...]:
        result = list(self._definitions.values())
        if workflow_type is not None:
            result = [d for d in result if d.workflow_type == workflow_type]
        return tuple(copy.deepcopy(d) for d in result)

    async def delete(self, definition_id: str) -> bool:
        return self._definitions.pop(definition_id, None) is not None


class FakeWorkflowExecutionRepository:
    """In-memory workflow execution repository for tests."""

    def __init__(self) -> None:
        self._executions: dict[str, WorkflowExecution] = {}

    async def save(self, execution: WorkflowExecution) -> None:
        stored = self._executions.get(execution.id)
        if stored is None:
            if execution.version != 1:
                msg = (
                    f"Cannot insert execution {execution.id!r}"
                    f" with version {execution.version}"
                )
                raise VersionConflictError(msg)
        else:
            if execution.version == 1:
                msg = f"Execution {execution.id!r} already exists"
                raise DuplicateRecordError(msg)
            if execution.version != stored.version + 1:
                msg = (
                    f"Version conflict: expected {stored.version + 1},"
                    f" got {execution.version}"
                )
                raise VersionConflictError(msg)
        self._executions[execution.id] = copy.deepcopy(execution)

    async def get(self, execution_id: str) -> WorkflowExecution | None:
        stored = self._executions.get(execution_id)
        return copy.deepcopy(stored) if stored is not None else None

    async def list_by_definition(
        self,
        definition_id: str,
    ) -> tuple[WorkflowExecution, ...]:
        result = sorted(
            [e for e in self._executions.values() if e.definition_id == definition_id],
            key=lambda e: e.updated_at,
            reverse=True,
        )
        return tuple(copy.deepcopy(e) for e in result)

    async def list_by_status(
        self,
        status: WorkflowExecutionStatus,
    ) -> tuple[WorkflowExecution, ...]:
        result = sorted(
            [e for e in self._executions.values() if e.status == status],
            key=lambda e: e.updated_at,
            reverse=True,
        )
        return tuple(copy.deepcopy(e) for e in result)

    async def find_by_task_id(
        self,
        task_id: str,
    ) -> WorkflowExecution | None:
        for execution in self._executions.values():
            if execution.status != WorkflowExecutionStatus.RUNNING:
                continue
            for ne in execution.node_executions:
                if ne.task_id == task_id:
                    return copy.deepcopy(execution)
        return None

    async def delete(self, execution_id: str) -> bool:
        return self._executions.pop(execution_id, None) is not None


class FakeWorkflowVersionRepository:
    """In-memory workflow version repository for tests."""

    def __init__(self) -> None:
        self._versions: dict[tuple[str, int], WorkflowDefinitionVersion] = {}

    async def save_version(
        self,
        version: WorkflowDefinitionVersion,
    ) -> None:
        key = (version.definition_id, version.version)
        if key not in self._versions:
            self._versions[key] = copy.deepcopy(version)

    async def get_version(
        self,
        definition_id: str,
        version: int,
    ) -> WorkflowDefinitionVersion | None:
        stored = self._versions.get((definition_id, version))
        return copy.deepcopy(stored) if stored is not None else None

    async def list_versions(
        self,
        definition_id: str,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[WorkflowDefinitionVersion, ...]:
        matching = sorted(
            (v for v in self._versions.values() if v.definition_id == definition_id),
            key=lambda v: v.version,
            reverse=True,
        )
        return tuple(copy.deepcopy(v) for v in matching[offset : offset + limit])

    async def count_versions(self, definition_id: str) -> int:
        return sum(
            1 for v in self._versions.values() if v.definition_id == definition_id
        )

    async def delete_versions_for_definition(self, definition_id: str) -> int:
        to_delete = [k for k in self._versions if k[0] == definition_id]
        for k in to_delete:
            del self._versions[k]
        return len(to_delete)
