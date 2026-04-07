"""In-memory ``PersistenceBackend`` fake for tests.

Extracted from ``tests/unit/api/fakes.py`` to keep that module under
the 800-line budget.  Re-exported from ``fakes`` for backwards
compatibility so existing test imports keep working.
"""

from typing import Any

from pydantic import AwareDatetime

from synthorg.core.types import NotBlankStr
from synthorg.security.rules.risk_override import RiskTierOverride
from synthorg.security.ssrf_violation import SsrfViolation, SsrfViolationStatus
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

__all__ = [
    "FakePersistenceBackend",
    "FakeRiskOverrideRepository",
    "FakeSsrfViolationRepository",
]


class FakeRiskOverrideRepository:
    """In-memory risk override repository for tests."""

    def __init__(self) -> None:
        self._overrides: dict[str, RiskTierOverride] = {}

    async def save(self, override: RiskTierOverride) -> None:
        self._overrides[override.id] = override

    async def get(
        self,
        override_id: NotBlankStr,
    ) -> RiskTierOverride | None:
        return self._overrides.get(override_id)

    async def list_active(self) -> tuple[RiskTierOverride, ...]:
        return tuple(o for o in self._overrides.values() if o.is_active)

    async def revoke(
        self,
        override_id: NotBlankStr,
        *,
        revoked_by: NotBlankStr,
        revoked_at: AwareDatetime,
    ) -> bool:
        ovr = self._overrides.get(override_id)
        if ovr is None or not ovr.is_active:
            return False
        self._overrides[override_id] = ovr.model_copy(
            update={"revoked_at": revoked_at, "revoked_by": revoked_by},
        )
        return True


class FakeSsrfViolationRepository:
    """In-memory SSRF violation repository for tests."""

    def __init__(self) -> None:
        self._violations: dict[str, SsrfViolation] = {}

    async def save(self, violation: SsrfViolation) -> None:
        self._violations[violation.id] = violation

    async def get(
        self,
        violation_id: NotBlankStr,
    ) -> SsrfViolation | None:
        return self._violations.get(violation_id)

    async def list_violations(
        self,
        *,
        status: SsrfViolationStatus | None = None,
        limit: int = 100,
    ) -> tuple[SsrfViolation, ...]:
        items = list(self._violations.values())
        if status is not None:
            items = [v for v in items if v.status == status]
        return tuple(items[:limit])

    async def update_status(
        self,
        violation_id: NotBlankStr,
        *,
        status: SsrfViolationStatus,
        resolved_by: NotBlankStr,
        resolved_at: AwareDatetime,
    ) -> bool:
        if status == SsrfViolationStatus.PENDING:
            msg = "Cannot transition a violation back to PENDING"
            raise ValueError(msg)
        v = self._violations.get(violation_id)
        if v is None or v.status != SsrfViolationStatus.PENDING:
            return False
        self._violations[violation_id] = v.model_copy(
            update={
                "status": status,
                "resolved_by": resolved_by,
                "resolved_at": resolved_at,
            },
        )
        return True


class FakePersistenceBackend:
    """In-memory persistence backend for tests."""

    def __init__(self) -> None:
        self._artifacts = FakeArtifactRepository()
        self._projects = FakeProjectRepository()
        self._custom_presets = FakePersonalityPresetRepository()
        self._workflow_definitions = FakeWorkflowDefinitionRepository()
        self._workflow_executions = FakeWorkflowExecutionRepository()
        self._workflow_versions = FakeWorkflowVersionRepository()
        self._risk_overrides = FakeRiskOverrideRepository()
        self._ssrf_violations = FakeSsrfViolationRepository()
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

    @property
    def risk_overrides(self) -> FakeRiskOverrideRepository:
        return self._risk_overrides

    @property
    def ssrf_violations(self) -> FakeSsrfViolationRepository:
        return self._ssrf_violations

    async def get_setting(self, key: str) -> str | None:
        return self._settings.get(key)

    async def set_setting(self, key: str, value: str) -> None:
        self._settings[key] = value
