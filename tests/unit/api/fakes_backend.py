"""In-memory ``PersistenceBackend`` fake for tests.

Extracted from ``tests/unit/api/fakes.py`` to keep that module under
the 800-line budget.  Re-exported from ``fakes`` for backwards
compatibility so existing test imports keep working.
"""

from typing import Any

from tests.unit.api.fakes import (
    FakeAgentStateRepository,
    FakeApiKeyRepository,
    FakeArtifactRepository,
    FakeAuditRepository,
    FakeCheckpointRepository,
    FakeCollaborationMetricRepository,
    FakeCostRecordRepository,
    FakeDecisionRepository,
    FakeHeartbeatRepository,
    FakeLifecycleEventRepository,
    FakeMessageRepository,
    FakeParkedContextRepository,
    FakePersonalityPresetRepository,
    FakeProjectRepository,
    FakeSettingsRepository,
    FakeTaskMetricRepository,
    FakeTaskRepository,
    FakeUserRepository,
)
from tests.unit.api.fakes_workflow import (
    FakeWorkflowDefinitionRepository,
    FakeWorkflowExecutionRepository,
    FakeWorkflowVersionRepository,
)

__all__ = ["FakePersistenceBackend"]


class FakePersistenceBackend:
    """In-memory persistence backend for tests."""

    def __init__(self) -> None:
        self._artifacts = FakeArtifactRepository()
        self._projects = FakeProjectRepository()
        self._custom_presets = FakePersonalityPresetRepository()
        self._workflow_definitions = FakeWorkflowDefinitionRepository()
        self._workflow_executions = FakeWorkflowExecutionRepository()
        self._workflow_versions = FakeWorkflowVersionRepository()
        self._tasks = FakeTaskRepository()
        self._cost_records = FakeCostRecordRepository()
        self._messages = FakeMessageRepository()
        self._lifecycle_events = FakeLifecycleEventRepository()
        self._task_metrics = FakeTaskMetricRepository()
        self._collaboration_metrics = FakeCollaborationMetricRepository()
        self._parked_contexts = FakeParkedContextRepository()
        self._audit_entries = FakeAuditRepository()
        self._decision_records = FakeDecisionRepository()
        self._users = FakeUserRepository()
        self._api_keys = FakeApiKeyRepository()
        self._checkpoints = FakeCheckpointRepository()
        self._heartbeats = FakeHeartbeatRepository()
        self._agent_states = FakeAgentStateRepository()
        self._settings_repo = FakeSettingsRepository()
        # Legacy flat KV store for get_setting/set_setting (pre-namespaced).
        # The `settings` property returns `_settings_repo` (namespaced repo).
        self._settings: dict[str, str] = {}
        self._connected = False

    async def connect(self) -> None:
        self._connected = True

    async def disconnect(self) -> None:
        self._connected = False

    def get_db(self) -> Any:
        msg = "FakePersistenceBackend does not expose a real DB"
        raise NotImplementedError(msg)

    async def health_check(self) -> bool:
        return self._connected

    async def migrate(self) -> None:
        pass

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def backend_name(self) -> str:
        return "fake"

    @property
    def artifacts(self) -> FakeArtifactRepository:
        return self._artifacts

    @property
    def projects(self) -> FakeProjectRepository:
        return self._projects

    @property
    def tasks(self) -> FakeTaskRepository:
        return self._tasks

    @property
    def cost_records(self) -> FakeCostRecordRepository:
        return self._cost_records

    @property
    def messages(self) -> FakeMessageRepository:
        return self._messages

    @property
    def lifecycle_events(self) -> FakeLifecycleEventRepository:
        return self._lifecycle_events

    @property
    def task_metrics(self) -> FakeTaskMetricRepository:
        return self._task_metrics

    @property
    def collaboration_metrics(self) -> FakeCollaborationMetricRepository:
        return self._collaboration_metrics

    @property
    def parked_contexts(self) -> FakeParkedContextRepository:
        return self._parked_contexts

    @property
    def audit_entries(self) -> FakeAuditRepository:
        return self._audit_entries

    @property
    def decision_records(self) -> FakeDecisionRepository:
        return self._decision_records

    @property
    def users(self) -> FakeUserRepository:
        return self._users

    @property
    def api_keys(self) -> FakeApiKeyRepository:
        return self._api_keys

    @property
    def checkpoints(self) -> FakeCheckpointRepository:
        return self._checkpoints

    @property
    def heartbeats(self) -> FakeHeartbeatRepository:
        return self._heartbeats

    @property
    def agent_states(self) -> FakeAgentStateRepository:
        return self._agent_states

    @property
    def settings(self) -> FakeSettingsRepository:
        return self._settings_repo

    @property
    def custom_presets(self) -> FakePersonalityPresetRepository:
        return self._custom_presets

    @property
    def workflow_definitions(self) -> FakeWorkflowDefinitionRepository:
        return self._workflow_definitions

    @property
    def workflow_executions(self) -> FakeWorkflowExecutionRepository:
        return self._workflow_executions

    @property
    def workflow_versions(self) -> FakeWorkflowVersionRepository:
        return self._workflow_versions

    async def get_setting(self, key: str) -> str | None:
        return self._settings.get(key)

    async def set_setting(self, key: str, value: str) -> None:
        self._settings[key] = value
