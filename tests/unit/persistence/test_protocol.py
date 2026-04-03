"""Tests for persistence protocol compliance."""

from typing import TYPE_CHECKING

import pytest

from synthorg.api.guards import HumanRole
from synthorg.core.types import NotBlankStr
from synthorg.hr.persistence_protocol import (
    CollaborationMetricRepository,
    LifecycleEventRepository,
    TaskMetricRepository,
)
from synthorg.persistence.preset_repository import (
    PersonalityPresetRepository,
    PresetListRow,
    PresetRow,
)
from synthorg.persistence.protocol import PersistenceBackend
from synthorg.persistence.repositories import (
    AgentStateRepository,
    ApiKeyRepository,
    ArtifactRepository,
    AuditRepository,
    CheckpointRepository,
    CostRecordRepository,
    HeartbeatRepository,
    MessageRepository,
    ParkedContextRepository,
    ProjectRepository,
    SettingsRepository,
    TaskRepository,
    UserRepository,
)
from synthorg.persistence.workflow_definition_repo import WorkflowDefinitionRepository

if TYPE_CHECKING:
    from pydantic import AwareDatetime

    from synthorg.api.auth.models import ApiKey, User
    from synthorg.budget.cost_record import CostRecord
    from synthorg.communication.message import Message
    from synthorg.core.artifact import Artifact
    from synthorg.core.enums import (
        ApprovalRiskLevel,
        ArtifactType,
        ProjectStatus,
        TaskStatus,
        WorkflowType,
    )
    from synthorg.core.project import Project
    from synthorg.core.task import Task
    from synthorg.engine.agent_state import AgentRuntimeState
    from synthorg.engine.checkpoint.models import Checkpoint, Heartbeat
    from synthorg.engine.workflow.definition import WorkflowDefinition
    from synthorg.hr.enums import LifecycleEventType
    from synthorg.hr.models import AgentLifecycleEvent
    from synthorg.hr.performance.models import (
        CollaborationMetricRecord,
        TaskMetricRecord,
    )
    from synthorg.security.models import AuditEntry, AuditVerdictStr
    from synthorg.security.timeout.parked_context import ParkedContext


class _FakeTaskRepository:
    async def save(self, task: Task) -> None:
        pass

    async def get(self, task_id: str) -> Task | None:
        return None

    async def list_tasks(
        self,
        *,
        status: TaskStatus | None = None,
        assigned_to: str | None = None,
        project: str | None = None,
    ) -> tuple[Task, ...]:
        return ()

    async def delete(self, task_id: str) -> bool:
        return False


class _FakeCostRecordRepository:
    async def save(self, record: CostRecord) -> None:
        pass

    async def query(
        self,
        *,
        agent_id: str | None = None,
        task_id: str | None = None,
    ) -> tuple[CostRecord, ...]:
        return ()

    async def aggregate(
        self,
        *,
        agent_id: str | None = None,
        task_id: str | None = None,
    ) -> float:
        return 0.0


class _FakeMessageRepository:
    async def save(self, message: Message) -> None:
        pass

    async def get_history(
        self,
        channel: str,
        *,
        limit: int | None = None,
    ) -> tuple[Message, ...]:
        return ()


class _FakeLifecycleEventRepository:
    async def save(self, event: AgentLifecycleEvent) -> None:
        pass

    async def list_events(
        self,
        *,
        agent_id: NotBlankStr | None = None,
        event_type: LifecycleEventType | None = None,
        since: AwareDatetime | None = None,
        limit: int | None = None,
    ) -> tuple[AgentLifecycleEvent, ...]:
        return ()


class _FakeTaskMetricRepository:
    async def save(self, record: TaskMetricRecord) -> None:
        pass

    async def query(
        self,
        *,
        agent_id: NotBlankStr | None = None,
        since: AwareDatetime | None = None,
        until: AwareDatetime | None = None,
    ) -> tuple[TaskMetricRecord, ...]:
        return ()


class _FakeCollaborationMetricRepository:
    async def save(
        self,
        record: CollaborationMetricRecord,
    ) -> None:
        pass

    async def query(
        self,
        *,
        agent_id: NotBlankStr | None = None,
        since: AwareDatetime | None = None,
    ) -> tuple[CollaborationMetricRecord, ...]:
        return ()


class _FakeParkedContextRepository:
    async def save(self, context: ParkedContext) -> None:
        pass

    async def get(self, parked_id: str) -> ParkedContext | None:
        return None

    async def get_by_approval(self, approval_id: str) -> ParkedContext | None:
        return None

    async def get_by_agent(self, agent_id: str) -> tuple[ParkedContext, ...]:
        return ()

    async def delete(self, parked_id: str) -> bool:
        return False


class _FakeAuditRepository:
    async def save(self, entry: AuditEntry) -> None:
        pass

    async def query(  # noqa: PLR0913
        self,
        *,
        agent_id: str | None = None,
        action_type: str | None = None,
        verdict: AuditVerdictStr | None = None,
        risk_level: ApprovalRiskLevel | None = None,
        since: AwareDatetime | None = None,
        until: AwareDatetime | None = None,
        limit: int = 100,
    ) -> tuple[AuditEntry, ...]:
        return ()


class _FakeUserRepository:
    async def save(self, user: User) -> None:
        pass

    async def get(self, user_id: str) -> User | None:
        return None

    async def get_by_username(self, username: str) -> User | None:
        return None

    async def list_users(self) -> tuple[User, ...]:
        return ()

    async def count(self) -> int:
        return 0

    async def count_by_role(self, role: HumanRole) -> int:
        return 0

    async def delete(self, user_id: str) -> bool:
        return False


class _FakeApiKeyRepository:
    async def save(self, key: ApiKey) -> None:
        pass

    async def get(self, key_id: str) -> ApiKey | None:
        return None

    async def get_by_hash(self, key_hash: str) -> ApiKey | None:
        return None

    async def list_by_user(self, user_id: str) -> tuple[ApiKey, ...]:
        return ()

    async def delete(self, key_id: str) -> bool:
        return False


class _FakeCheckpointRepository:
    async def save(self, checkpoint: Checkpoint) -> None:
        pass

    async def get_latest(
        self,
        *,
        execution_id: str | None = None,
        task_id: str | None = None,
    ) -> Checkpoint | None:
        return None

    async def delete_by_execution(self, execution_id: str) -> int:
        return 0


class _FakeHeartbeatRepository:
    async def save(self, heartbeat: Heartbeat) -> None:
        pass

    async def get(self, execution_id: str) -> Heartbeat | None:
        return None

    async def get_stale(
        self,
        threshold: AwareDatetime,
    ) -> tuple[Heartbeat, ...]:
        return ()

    async def delete(self, execution_id: str) -> bool:
        return False


class _FakeAgentStateRepository:
    async def save(self, state: AgentRuntimeState) -> None:
        pass

    async def get(self, agent_id: str) -> AgentRuntimeState | None:
        return None

    async def get_active(self) -> tuple[AgentRuntimeState, ...]:
        return ()

    async def delete(self, agent_id: str) -> bool:
        return False


class _FakeSettingsRepository:
    async def get(self, namespace: str, key: str) -> tuple[str, str] | None:
        return None

    async def get_namespace(self, namespace: str) -> tuple[tuple[str, str, str], ...]:
        return ()

    async def get_all(self) -> tuple[tuple[str, str, str, str], ...]:
        return ()

    async def set(self, namespace: str, key: str, value: str, updated_at: str) -> None:
        pass

    async def delete(self, namespace: str, key: str) -> bool:
        return False

    async def delete_namespace(self, namespace: str) -> int:
        return 0


class _FakeArtifactRepository:
    async def save(self, artifact: Artifact) -> None:
        pass

    async def get(self, artifact_id: NotBlankStr) -> Artifact | None:
        return None

    async def list_artifacts(
        self,
        *,
        task_id: NotBlankStr | None = None,
        created_by: NotBlankStr | None = None,
        artifact_type: ArtifactType | None = None,
    ) -> tuple[Artifact, ...]:
        return ()

    async def delete(self, artifact_id: NotBlankStr) -> bool:
        return False


class _FakeProjectRepository:
    async def save(self, project: Project) -> None:
        pass

    async def get(self, project_id: NotBlankStr) -> Project | None:
        return None

    async def list_projects(
        self,
        *,
        status: ProjectStatus | None = None,
        lead: NotBlankStr | None = None,
    ) -> tuple[Project, ...]:
        return ()

    async def delete(self, project_id: NotBlankStr) -> bool:
        return False


class _FakePersonalityPresetRepository:
    async def save(
        self,
        name: NotBlankStr,
        config_json: str,
        description: str,
        created_at: str,
        updated_at: str,
    ) -> None:
        pass

    async def get(
        self,
        name: NotBlankStr,
    ) -> PresetRow | None:
        return None

    async def list_all(self) -> tuple[PresetListRow, ...]:
        return ()

    async def delete(self, name: NotBlankStr) -> bool:
        return False

    async def count(self) -> int:
        return 0


class _FakeWorkflowDefinitionRepository:
    async def save(self, definition: WorkflowDefinition) -> None:
        pass

    async def get(self, definition_id: NotBlankStr) -> WorkflowDefinition | None:
        return None

    async def list_definitions(
        self,
        *,
        workflow_type: WorkflowType | None = None,
    ) -> tuple[WorkflowDefinition, ...]:
        return ()

    async def delete(self, definition_id: NotBlankStr) -> bool:
        return False


class _FakeBackend:
    async def connect(self) -> None:
        pass

    async def disconnect(self) -> None:
        pass

    async def health_check(self) -> bool:
        return True

    async def migrate(self) -> None:
        pass

    def get_db(self) -> object:
        msg = "Not supported"
        raise NotImplementedError(msg)

    @property
    def is_connected(self) -> bool:
        return True

    @property
    def backend_name(self) -> NotBlankStr:
        return NotBlankStr("fake")

    @property
    def tasks(self) -> _FakeTaskRepository:
        return _FakeTaskRepository()

    @property
    def cost_records(self) -> _FakeCostRecordRepository:
        return _FakeCostRecordRepository()

    @property
    def messages(self) -> _FakeMessageRepository:
        return _FakeMessageRepository()

    @property
    def lifecycle_events(self) -> _FakeLifecycleEventRepository:
        return _FakeLifecycleEventRepository()

    @property
    def task_metrics(self) -> _FakeTaskMetricRepository:
        return _FakeTaskMetricRepository()

    @property
    def parked_contexts(self) -> _FakeParkedContextRepository:
        return _FakeParkedContextRepository()

    @property
    def collaboration_metrics(self) -> _FakeCollaborationMetricRepository:
        return _FakeCollaborationMetricRepository()

    @property
    def audit_entries(self) -> _FakeAuditRepository:
        return _FakeAuditRepository()

    @property
    def users(self) -> _FakeUserRepository:
        return _FakeUserRepository()

    @property
    def api_keys(self) -> _FakeApiKeyRepository:
        return _FakeApiKeyRepository()

    @property
    def checkpoints(self) -> _FakeCheckpointRepository:
        return _FakeCheckpointRepository()

    @property
    def heartbeats(self) -> _FakeHeartbeatRepository:
        return _FakeHeartbeatRepository()

    @property
    def agent_states(self) -> _FakeAgentStateRepository:
        return _FakeAgentStateRepository()

    @property
    def settings(self) -> _FakeSettingsRepository:
        return _FakeSettingsRepository()

    @property
    def artifacts(self) -> _FakeArtifactRepository:
        return _FakeArtifactRepository()

    @property
    def projects(self) -> _FakeProjectRepository:
        return _FakeProjectRepository()

    @property
    def custom_presets(self) -> _FakePersonalityPresetRepository:
        return _FakePersonalityPresetRepository()

    @property
    def workflow_definitions(self) -> _FakeWorkflowDefinitionRepository:
        return _FakeWorkflowDefinitionRepository()

    async def get_setting(self, key: str) -> str | None:
        return None

    async def set_setting(self, key: str, value: str) -> None:
        pass


@pytest.mark.unit
class TestProtocolCompliance:
    def test_fake_backend_is_persistence_backend(self) -> None:
        assert isinstance(_FakeBackend(), PersistenceBackend)

    def test_fake_task_repo_is_task_repository(self) -> None:
        assert isinstance(_FakeTaskRepository(), TaskRepository)

    def test_fake_cost_repo_is_cost_record_repository(self) -> None:
        assert isinstance(_FakeCostRecordRepository(), CostRecordRepository)

    def test_fake_message_repo_is_message_repository(self) -> None:
        assert isinstance(_FakeMessageRepository(), MessageRepository)

    def test_fake_lifecycle_repo_is_lifecycle_event_repository(self) -> None:
        assert isinstance(_FakeLifecycleEventRepository(), LifecycleEventRepository)

    def test_fake_task_metric_repo_is_task_metric_repository(self) -> None:
        assert isinstance(_FakeTaskMetricRepository(), TaskMetricRepository)

    def test_fake_collab_metric_repo_is_collaboration_metric_repository(
        self,
    ) -> None:
        assert isinstance(
            _FakeCollaborationMetricRepository(),
            CollaborationMetricRepository,
        )

    def test_fake_parked_context_repo_is_parked_context_repository(
        self,
    ) -> None:
        assert isinstance(
            _FakeParkedContextRepository(),
            ParkedContextRepository,
        )

    def test_fake_audit_repo_is_audit_repository(self) -> None:
        assert isinstance(_FakeAuditRepository(), AuditRepository)

    def test_fake_user_repo_is_user_repository(self) -> None:
        assert isinstance(_FakeUserRepository(), UserRepository)

    def test_fake_api_key_repo_is_api_key_repository(self) -> None:
        assert isinstance(_FakeApiKeyRepository(), ApiKeyRepository)

    def test_fake_checkpoint_repo_is_checkpoint_repository(self) -> None:
        assert isinstance(_FakeCheckpointRepository(), CheckpointRepository)

    def test_fake_heartbeat_repo_is_heartbeat_repository(self) -> None:
        assert isinstance(_FakeHeartbeatRepository(), HeartbeatRepository)

    def test_fake_agent_state_repo_is_agent_state_repository(self) -> None:
        assert isinstance(_FakeAgentStateRepository(), AgentStateRepository)

    def test_fake_settings_repo_is_settings_repository(self) -> None:
        assert isinstance(_FakeSettingsRepository(), SettingsRepository)

    def test_fake_artifact_repo_is_artifact_repository(self) -> None:
        assert isinstance(_FakeArtifactRepository(), ArtifactRepository)

    def test_fake_project_repo_is_project_repository(self) -> None:
        assert isinstance(_FakeProjectRepository(), ProjectRepository)

    def test_fake_preset_repo_is_personality_preset_repository(self) -> None:
        assert isinstance(
            _FakePersonalityPresetRepository(),
            PersonalityPresetRepository,
        )

    def test_fake_workflow_def_repo_is_workflow_definition_repository(
        self,
    ) -> None:
        assert isinstance(
            _FakeWorkflowDefinitionRepository(),
            WorkflowDefinitionRepository,
        )
