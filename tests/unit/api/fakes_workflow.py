"""In-memory fake workflow repositories for API unit tests."""

import copy
from typing import TYPE_CHECKING

from synthorg.core.enums import WorkflowExecutionStatus
from synthorg.persistence.errors import DuplicateRecordError, VersionConflictError

if TYPE_CHECKING:
    from synthorg.core.enums import WorkflowType
    from synthorg.core.types import NotBlankStr
    from synthorg.engine.workflow.definition import WorkflowDefinition
    from synthorg.engine.workflow.execution_models import WorkflowExecution
    from synthorg.versioning import VersionSnapshot


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
    """In-memory workflow version repository for tests.

    Implements ``VersionRepository[WorkflowDefinition]`` protocol.
    """

    def __init__(self) -> None:
        self._versions: dict[
            tuple[str, int],
            VersionSnapshot[WorkflowDefinition],
        ] = {}

    async def save_version(
        self,
        version: VersionSnapshot[WorkflowDefinition],
    ) -> bool:
        key = (version.entity_id, version.version)
        if key in self._versions:
            return False
        self._versions[key] = copy.deepcopy(version)
        return True

    async def get_version(
        self,
        entity_id: NotBlankStr,
        version: int,
    ) -> VersionSnapshot[WorkflowDefinition] | None:
        stored = self._versions.get((entity_id, version))
        return copy.deepcopy(stored) if stored is not None else None

    async def get_latest_version(
        self,
        entity_id: NotBlankStr,
    ) -> VersionSnapshot[WorkflowDefinition] | None:
        matching = [v for v in self._versions.values() if v.entity_id == entity_id]
        if not matching:
            return None
        latest = max(matching, key=lambda v: v.version)
        return copy.deepcopy(latest)

    async def get_by_content_hash(
        self,
        entity_id: NotBlankStr,
        content_hash: NotBlankStr,
    ) -> VersionSnapshot[WorkflowDefinition] | None:
        matches = [
            v
            for v in self._versions.values()
            if v.entity_id == entity_id and v.content_hash == content_hash
        ]
        if not matches:
            return None
        latest = max(matches, key=lambda v: v.version)
        return copy.deepcopy(latest)

    async def list_versions(
        self,
        entity_id: NotBlankStr,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[VersionSnapshot[WorkflowDefinition], ...]:
        if limit < 0 or offset < 0:
            msg = (
                f"limit and offset must be non-negative "
                f"(got limit={limit}, offset={offset})"
            )
            raise ValueError(msg)
        matching = sorted(
            (v for v in self._versions.values() if v.entity_id == entity_id),
            key=lambda v: v.version,
            reverse=True,
        )
        return tuple(copy.deepcopy(v) for v in matching[offset : offset + limit])

    async def count_versions(self, entity_id: NotBlankStr) -> int:
        return sum(1 for v in self._versions.values() if v.entity_id == entity_id)

    async def delete_versions_for_entity(
        self,
        entity_id: NotBlankStr,
    ) -> int:
        to_delete = [k for k in self._versions if k[0] == entity_id]
        for k in to_delete:
            del self._versions[k]
        return len(to_delete)
