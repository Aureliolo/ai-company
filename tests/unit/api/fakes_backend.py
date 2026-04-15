"""In-memory ``PersistenceBackend`` fake for tests.

Extracted from ``tests/unit/api/fakes.py`` to keep that module under
the 800-line budget.  Imports point directly at the extracted modules
(``fake_user_repository``, ``fakes``).
"""

from typing import Any

from pydantic import AwareDatetime

from synthorg.core.types import NotBlankStr
from synthorg.hr.training.models import TrainingPlan, TrainingPlanStatus, TrainingResult
from synthorg.meta.rules.custom import CustomRuleDefinition
from synthorg.persistence.errors import DuplicateRecordError
from synthorg.persistence.integration_stubs import (
    StubConnectionRepository,
    StubConnectionSecretRepository,
    StubOAuthStateRepository,
    StubWebhookReceiptRepository,
)
from synthorg.security.rules.risk_override import RiskTierOverride
from synthorg.security.ssrf_violation import SsrfViolation, SsrfViolationStatus
from synthorg.versioning.models import VersionSnapshot
from tests.unit.api.fake_user_repository import FakeUserRepository
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
)
from tests.unit.api.fakes_workflow import (
    FakeSubworkflowRepository,
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
        if override.id in self._overrides:
            msg = f"Risk override {override.id!r} already exists"
            raise DuplicateRecordError(msg)
        self._overrides[override.id] = override

    async def get(
        self,
        override_id: NotBlankStr,
    ) -> RiskTierOverride | None:
        return self._overrides.get(override_id)

    async def list_active(self) -> tuple[RiskTierOverride, ...]:
        active = [o for o in self._overrides.values() if o.is_active]
        active.sort(key=lambda o: o.created_at, reverse=True)
        return tuple(active)

    async def revoke(
        self,
        override_id: NotBlankStr,
        *,
        revoked_by: NotBlankStr,
        revoked_at: AwareDatetime,
    ) -> bool:
        ovr = self._overrides.get(override_id)
        if ovr is None or ovr.revoked_at is not None:
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
        if violation.id in self._violations:
            msg = f"SSRF violation {violation.id!r} already exists"
            raise DuplicateRecordError(msg)
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
        if limit <= 0:
            msg = "limit must be positive"
            raise ValueError(msg)
        items = list(self._violations.values())
        if status is not None:
            items = [v for v in items if v.status == status]
        items.sort(key=lambda v: v.timestamp, reverse=True)
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


class FakeCircuitBreakerStateRepository:
    """In-memory circuit breaker state repository for tests."""

    def __init__(self) -> None:
        from synthorg.persistence.circuit_breaker_repo import (
            CircuitBreakerStateRecord,
        )

        self._store: dict[tuple[str, str], CircuitBreakerStateRecord] = {}

    async def save(self, record: Any) -> None:
        self._store[(record.pair_key_a, record.pair_key_b)] = record

    async def load_all(self) -> tuple[Any, ...]:
        return tuple(self._store.values())

    async def delete(self, pair_key_a: str, pair_key_b: str) -> bool:
        key = (pair_key_a, pair_key_b)
        if key in self._store:
            del self._store[key]
            return True
        return False


class FakeVersionRepository:
    """In-memory VersionRepository for tests (any snapshot type)."""

    def __init__(self) -> None:
        self._store: dict[tuple[str, int], VersionSnapshot[Any]] = {}

    async def save_version(self, version: VersionSnapshot[Any]) -> bool:
        key = (version.entity_id, version.version)
        was_new = key not in self._store
        self._store.setdefault(key, version)
        return was_new

    async def get_version(
        self, entity_id: NotBlankStr, version: int
    ) -> VersionSnapshot[Any] | None:
        return self._store.get((entity_id, version))

    async def get_latest_version(
        self, entity_id: NotBlankStr
    ) -> VersionSnapshot[Any] | None:
        candidates = [v for (eid, _), v in self._store.items() if eid == entity_id]
        return max(candidates, key=lambda v: v.version) if candidates else None

    async def get_by_content_hash(
        self, entity_id: NotBlankStr, content_hash: NotBlankStr
    ) -> VersionSnapshot[Any] | None:
        for (eid, _), v in self._store.items():
            if eid == entity_id and v.content_hash == content_hash:
                return v
        return None

    async def list_versions(
        self,
        entity_id: NotBlankStr,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[VersionSnapshot[Any], ...]:
        candidates = sorted(
            (v for (eid, _), v in self._store.items() if eid == entity_id),
            key=lambda v: v.version,
            reverse=True,
        )
        return tuple(candidates[offset : offset + limit])

    async def count_versions(self, entity_id: NotBlankStr) -> int:
        return sum(1 for eid, _ in self._store if eid == entity_id)

    async def delete_versions_for_entity(self, entity_id: NotBlankStr) -> int:
        to_delete = [k for k in self._store if k[0] == entity_id]
        for k in to_delete:
            del self._store[k]
        return len(to_delete)


class FakeTrainingPlanRepository:
    """In-memory fake for ``TrainingPlanRepository``."""

    def __init__(self) -> None:
        self._plans: dict[str, TrainingPlan] = {}

    async def save(self, plan: TrainingPlan) -> None:
        self._plans[str(plan.id)] = plan

    async def get(self, plan_id: NotBlankStr) -> TrainingPlan | None:
        return self._plans.get(str(plan_id))

    async def latest_pending(
        self,
        agent_id: NotBlankStr,
    ) -> TrainingPlan | None:
        pending = [
            p
            for p in self._plans.values()
            if str(p.new_agent_id) == str(agent_id)
            and p.status == TrainingPlanStatus.PENDING
        ]
        if not pending:
            return None
        return max(pending, key=lambda p: p.created_at)

    async def list_by_agent(
        self,
        agent_id: NotBlankStr,
    ) -> tuple[TrainingPlan, ...]:
        plans = [
            p for p in self._plans.values() if str(p.new_agent_id) == str(agent_id)
        ]
        return tuple(sorted(plans, key=lambda p: p.created_at, reverse=True))


class FakeTrainingResultRepository:
    """In-memory fake for ``TrainingResultRepository``."""

    def __init__(self) -> None:
        self._results: dict[str, TrainingResult] = {}

    async def save(self, result: TrainingResult) -> None:
        plan_key = str(result.plan_id)
        for rid, r in self._results.items():
            if str(r.plan_id) == plan_key and rid != str(result.id):
                msg = f"UNIQUE constraint: plan_id {plan_key!r} already exists"
                raise ValueError(msg)
        self._results[str(result.id)] = result

    async def get_by_plan(
        self,
        plan_id: NotBlankStr,
    ) -> TrainingResult | None:
        for r in self._results.values():
            if str(r.plan_id) == str(plan_id):
                return r
        return None

    async def get_latest(
        self,
        agent_id: NotBlankStr,
    ) -> TrainingResult | None:
        agent_results = [
            r for r in self._results.values() if str(r.new_agent_id) == str(agent_id)
        ]
        if not agent_results:
            return None
        return max(agent_results, key=lambda r: r.completed_at)


class FakeCustomRuleRepository:
    """In-memory fake for ``CustomRuleRepository``."""

    def __init__(self) -> None:
        self._rules: dict[str, CustomRuleDefinition] = {}

    async def save(self, rule: CustomRuleDefinition) -> None:
        from synthorg.persistence.errors import (
            ConstraintViolationError,
        )

        for existing in self._rules.values():
            if existing.name == rule.name and existing.id != rule.id:
                msg = f"Custom rule name '{rule.name}' already exists"
                raise ConstraintViolationError(
                    msg,
                    constraint="custom_rules_name_unique",
                )
        self._rules[str(rule.id)] = rule

    async def get(
        self,
        rule_id: NotBlankStr,
    ) -> CustomRuleDefinition | None:
        return self._rules.get(str(rule_id))

    async def get_by_name(
        self,
        name: NotBlankStr,
    ) -> CustomRuleDefinition | None:
        for r in self._rules.values():
            if r.name == name:
                return r
        return None

    async def list_rules(
        self,
        *,
        enabled_only: bool = False,
    ) -> tuple[CustomRuleDefinition, ...]:
        rules = list(self._rules.values())
        if enabled_only:
            rules = [r for r in rules if r.enabled]
        return tuple(sorted(rules, key=lambda r: r.name))

    async def delete(self, rule_id: NotBlankStr) -> bool:
        key = str(rule_id)
        if key in self._rules:
            del self._rules[key]
            return True
        return False


class FakePersistenceBackend:
    """In-memory persistence backend for tests."""

    def __init__(self) -> None:
        self._artifacts = FakeArtifactRepository()
        self._projects = FakeProjectRepository()
        self._custom_presets = FakePersonalityPresetRepository()
        self._workflow_definitions = FakeWorkflowDefinitionRepository()
        self._workflow_executions = FakeWorkflowExecutionRepository()
        self._workflow_versions = FakeWorkflowVersionRepository()
        self._subworkflows = FakeSubworkflowRepository(
            definition_repo=self._workflow_definitions,
        )
        self._identity_versions = FakeVersionRepository()
        self._evaluation_config_versions = FakeVersionRepository()
        self._budget_config_versions = FakeVersionRepository()
        self._company_versions = FakeVersionRepository()
        self._role_versions = FakeVersionRepository()
        self._risk_overrides = FakeRiskOverrideRepository()
        self._ssrf_violations = FakeSsrfViolationRepository()
        self._circuit_breaker_state = FakeCircuitBreakerStateRepository()
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
        self._training_plans_repo = FakeTrainingPlanRepository()
        self._training_results_repo = FakeTrainingResultRepository()
        self._custom_rules_repo = FakeCustomRuleRepository()
        self._connections_stub = StubConnectionRepository()
        self._connection_secrets_stub = StubConnectionSecretRepository()
        self._oauth_states_stub = StubOAuthStateRepository()
        self._webhook_receipts_stub = StubWebhookReceiptRepository()
        # Legacy flat KV store for get_setting/set_setting (pre-namespaced).
        # The `settings` property returns `_settings_repo` (namespaced repo).
        self._settings: dict[str, str] = {}
        self._connected = False

    def clear(self) -> None:
        """Reset all in-memory state for test isolation.

        Clears repository contents in-place so any services holding
        references to repository objects observe the reset.  Preserves
        object identity and the connection flag.
        """
        for attr_name in list(vars(self)):
            if attr_name == "_connected":
                continue
            value = getattr(self, attr_name)
            # Clear mutable containers directly.
            if isinstance(value, (dict, list, set)):
                value.clear()
                continue
            # Clear internal state of fake repository objects.
            for inner_value in vars(value).values():
                if isinstance(inner_value, (dict, list, set)):
                    inner_value.clear()

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
    def subworkflows(self) -> FakeSubworkflowRepository:
        return self._subworkflows

    @property
    def workflow_versions(self) -> FakeWorkflowVersionRepository:
        return self._workflow_versions

    @property
    def identity_versions(self) -> FakeVersionRepository:
        return self._identity_versions

    @property
    def evaluation_config_versions(self) -> FakeVersionRepository:
        return self._evaluation_config_versions

    @property
    def budget_config_versions(self) -> FakeVersionRepository:
        return self._budget_config_versions

    @property
    def company_versions(self) -> FakeVersionRepository:
        return self._company_versions

    @property
    def role_versions(self) -> FakeVersionRepository:
        return self._role_versions

    @property
    def risk_overrides(self) -> FakeRiskOverrideRepository:
        return self._risk_overrides

    @property
    def ssrf_violations(self) -> FakeSsrfViolationRepository:
        return self._ssrf_violations

    @property
    def circuit_breaker_state(self) -> FakeCircuitBreakerStateRepository:
        return self._circuit_breaker_state

    @property
    def connections(self) -> StubConnectionRepository:
        """Stub connection repository."""
        return self._connections_stub

    @property
    def connection_secrets(self) -> StubConnectionSecretRepository:
        """Stub connection secret repository."""
        return self._connection_secrets_stub

    @property
    def oauth_states(self) -> StubOAuthStateRepository:
        """Stub OAuth state repository."""
        return self._oauth_states_stub

    @property
    def webhook_receipts(self) -> StubWebhookReceiptRepository:
        """Stub webhook receipt repository."""
        return self._webhook_receipts_stub

    @property
    def training_plans(self) -> FakeTrainingPlanRepository:
        """Fake training plan repository."""
        return self._training_plans_repo

    @property
    def training_results(self) -> FakeTrainingResultRepository:
        """Fake training result repository."""
        return self._training_results_repo

    @property
    def custom_rules(self) -> FakeCustomRuleRepository:
        """Fake custom rule repository."""
        return self._custom_rules_repo

    async def get_setting(self, key: str) -> str | None:
        return self._settings.get(key)

    async def set_setting(self, key: str, value: str) -> None:
        self._settings[key] = value
