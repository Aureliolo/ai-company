"""Shared fixtures for API unit tests."""

import uuid
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from litestar import Litestar
from litestar.testing import TestClient

import synthorg.settings.definitions  # noqa: F401 -- trigger registration
from synthorg.api.app import create_app
from synthorg.api.approval_store import ApprovalStore
from synthorg.api.auth.config import AuthConfig
from synthorg.api.auth.models import User
from synthorg.api.auth.service import AuthService
from synthorg.api.exception_handlers import EXCEPTION_HANDLERS
from synthorg.api.guards import HumanRole
from synthorg.budget.tracker import CostTracker
from synthorg.communication.delegation.record_store import (
    DelegationRecordStore,
)
from synthorg.config.schema import RootConfig
from synthorg.core.approval import ApprovalItem
from synthorg.core.enums import (
    ApprovalRiskLevel,
    ApprovalStatus,
    TaskStatus,
)
from synthorg.core.task import Task
from synthorg.engine.task_engine import TaskEngine
from synthorg.hr.performance.tracker import PerformanceTracker
from synthorg.hr.registry import AgentRegistryService
from synthorg.providers.health import ProviderHealthTracker
from synthorg.settings.registry import get_registry
from synthorg.settings.service import SettingsService
from synthorg.tools.invocation_tracker import ToolInvocationTracker
from tests.unit.api.fakes import (
    FakeArtifactStorage,
    FakeMessageBus,
    FakePersistenceBackend,
)

__all__ = ["FakeMessageBus", "FakePersistenceBackend"]

# ── Test auth constants ───────────────────────────────────────

_TEST_JWT_SECRET = "test-secret-that-is-at-least-32-characters-long"
# Hardcoded valid Fernet key (deterministic across xdist workers).
_TEST_SETTINGS_KEY = "lKzZcMznksIF8A_2HFFUnKxhxhz9_bxTvVJoZ6mvZrk="
_TEST_USER_ID = "test-user-001"
_TEST_USERNAME = "testadmin"


@pytest.fixture(autouse=True)
def _required_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set SYNTHORG_JWT_SECRET and SYNTHORG_SETTINGS_KEY for API tests.

    The backend now requires both env vars at startup (no auto-generation).
    """
    monkeypatch.setenv("SYNTHORG_JWT_SECRET", _TEST_JWT_SECRET)
    monkeypatch.setenv("SYNTHORG_SETTINGS_KEY", _TEST_SETTINGS_KEY)


@pytest.fixture(autouse=True)
def _no_backup_service(monkeypatch: pytest.MonkeyPatch) -> None:
    """Disable the backup service in all API unit tests.

    ``create_app`` auto-builds a real ``BackupService`` from config,
    which triggers filesystem I/O (backup creation + retention
    pruning of tar.gz archives) on every app startup and shutdown.
    On Windows this adds 15-25 s per ``TestClient`` lifecycle due to
    Defender scanning each archive.  Patching the factory to return
    ``None`` eliminates this overhead.  Backup-specific behaviour is
    tested in ``tests/unit/backup/`` with dedicated mocks.
    """
    monkeypatch.setattr(
        "synthorg.api.app.build_backup_service",
        lambda *_a, **_kw: None,
    )


def make_exception_handler_app(handler: Any) -> Litestar:
    """Build a minimal Litestar app with project exception handlers."""
    return Litestar(
        route_handlers=[handler],
        exception_handlers=dict(EXCEPTION_HANDLERS),  # type: ignore[arg-type]
    )


# ── Auth helpers ────────────────────────────────────────────────

# Cache password hashes by role so that make_auth_headers and
# _seed_test_users produce identical pwd_sig claims.
_TEST_PASSWORD_HASHES: dict[str, str] = {}


def _make_test_auth_config() -> AuthConfig:
    """Create an AuthConfig with a test JWT secret."""
    return AuthConfig(jwt_secret=_TEST_JWT_SECRET)


def _make_test_auth_service() -> AuthService:
    """Create an AuthService backed by test config."""
    return AuthService(_make_test_auth_config())


def _get_test_password_hash(
    role: str,
    auth_service: AuthService,
) -> str:
    """Return a cached password hash for the given role.

    On the first call for a role, hashes the test password and
    caches the result so that ``make_auth_headers`` and
    ``_seed_test_users`` produce tokens with matching ``pwd_sig``
    claims.
    """
    if role not in _TEST_PASSWORD_HASHES:
        _TEST_PASSWORD_HASHES[role] = auth_service.hash_password(
            "test-password-12chars",
        )
    return _TEST_PASSWORD_HASHES[role]


def _make_test_user(
    *,
    role: HumanRole = HumanRole.CEO,
    must_change_password: bool = False,
    user_id: str = _TEST_USER_ID,
    username: str = _TEST_USERNAME,
) -> User:
    """Create a test User with given role."""
    now = datetime.now(UTC)
    auth_service = _make_test_auth_service()
    return User(
        id=user_id,
        username=username,
        password_hash=_get_test_password_hash(role.value, auth_service),
        role=role,
        must_change_password=must_change_password,
        created_at=now,
        updated_at=now,
    )


def make_auth_headers(
    role: str = "ceo",
    *,
    must_change_password: bool = False,
) -> dict[str, str]:
    """Build an Authorization header with a JWT for the given role.

    Uses deterministic user IDs matching ``_seed_test_users`` so
    middleware user lookups succeed.  The password hash is cached
    per role to ensure the ``pwd_sig`` claim matches the seeded
    user in persistence.
    """
    auth_service = _make_test_auth_service()
    # Must match the ID pattern in _seed_test_users
    user_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"test-{role}"))
    now = datetime.now(UTC)
    user = User(
        id=user_id,
        username=f"test-{role}",
        password_hash=_get_test_password_hash(role, auth_service),
        role=HumanRole(role),
        must_change_password=must_change_password,
        created_at=now,
        updated_at=now,
    )
    token, _, _ = auth_service.create_token(user)
    return {"Authorization": f"Bearer {token}"}


# ── Fixtures ────────────────────────────────────────────────────


@pytest.fixture
def auth_config() -> AuthConfig:
    return _make_test_auth_config()


@pytest.fixture
def auth_service() -> AuthService:
    return _make_test_auth_service()


@pytest.fixture
async def fake_persistence() -> FakePersistenceBackend:
    backend = FakePersistenceBackend()
    await backend.connect()
    return backend


@pytest.fixture
async def fake_message_bus() -> FakeMessageBus:
    bus = FakeMessageBus()
    await bus.start()
    return bus


@pytest.fixture
def cost_tracker() -> CostTracker:
    return CostTracker()


@pytest.fixture
def approval_store() -> ApprovalStore:
    return ApprovalStore()


@pytest.fixture
def root_config() -> RootConfig:
    return RootConfig(company_name="test-company")


@pytest.fixture
def performance_tracker() -> PerformanceTracker:
    return PerformanceTracker()


@pytest.fixture
def agent_registry() -> AgentRegistryService:
    """Return a fresh AgentRegistryService instance."""
    return AgentRegistryService()


@pytest.fixture
def provider_health_tracker() -> ProviderHealthTracker:
    """Return a fresh ProviderHealthTracker instance."""
    return ProviderHealthTracker()


@pytest.fixture
def tool_invocation_tracker() -> ToolInvocationTracker:
    """Return a fresh ToolInvocationTracker instance."""
    return ToolInvocationTracker()


@pytest.fixture
def delegation_record_store() -> DelegationRecordStore:
    """Return a fresh DelegationRecordStore instance."""
    return DelegationRecordStore()


@pytest.fixture
def fake_task_engine(
    fake_persistence: FakePersistenceBackend,
) -> TaskEngine:
    """TaskEngine backed by the shared fake persistence."""
    return TaskEngine(
        persistence=fake_persistence,
    )


@pytest.fixture
def test_client(  # noqa: PLR0913
    fake_persistence: FakePersistenceBackend,
    fake_message_bus: FakeMessageBus,
    cost_tracker: CostTracker,
    approval_store: ApprovalStore,
    root_config: RootConfig,
    auth_service: AuthService,
    fake_task_engine: TaskEngine,
    performance_tracker: PerformanceTracker,
    agent_registry: AgentRegistryService,
    provider_health_tracker: ProviderHealthTracker,
    tool_invocation_tracker: ToolInvocationTracker,
    delegation_record_store: DelegationRecordStore,
) -> Generator[TestClient[Any]]:
    # Pre-seed users for each role so JWT sub claims resolve
    _seed_test_users(fake_persistence, auth_service)

    settings_service = SettingsService(
        repository=fake_persistence.settings,
        registry=get_registry(),
        config=root_config,
    )

    app = create_app(
        config=root_config,
        persistence=fake_persistence,
        message_bus=fake_message_bus,
        cost_tracker=cost_tracker,
        approval_store=approval_store,
        auth_service=auth_service,
        task_engine=fake_task_engine,
        performance_tracker=performance_tracker,
        agent_registry=agent_registry,
        settings_service=settings_service,
        provider_health_tracker=provider_health_tracker,
        tool_invocation_tracker=tool_invocation_tracker,
        delegation_record_store=delegation_record_store,
        artifact_storage=FakeArtifactStorage(),
    )
    with TestClient(app) as client:
        # Default: CEO token (most tests need write access)
        client.headers.update(make_auth_headers("ceo"))
        yield client


def _seed_test_users(
    backend: FakePersistenceBackend,
    auth_service: AuthService,
) -> None:
    """Pre-seed a user for each role so JWT validation succeeds.

    The middleware looks up the user by ``sub`` claim, so we
    need matching users in the fake persistence for every role
    that tests might use.  Uses cached password hashes to ensure
    ``pwd_sig`` claims match between seeded users and tokens
    produced by ``make_auth_headers``.

    Assigns directly to the fake repository's internal dict
    (avoiding async) so this helper works in both sync fixtures
    and sync test functions.
    """
    now = datetime.now(UTC)
    for role in HumanRole:
        user_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"test-{role.value}"))
        user = User(
            id=user_id,
            username=f"test-{role.value}",
            password_hash=_get_test_password_hash(
                role.value,
                auth_service,
            ),
            role=role,
            must_change_password=False,
            created_at=now,
            updated_at=now,
        )
        backend._users._users[user.id] = user


def make_task(  # noqa: PLR0913
    *,
    task_id: str = "task-001",
    title: str = "Test task",
    description: str = "A test task",
    project: str = "test-project",
    created_by: str = "alice",
    status: TaskStatus = TaskStatus.CREATED,
    assigned_to: str | None = None,
) -> Task:
    """Build a Task with sensible defaults."""
    from synthorg.core.enums import TaskType

    if assigned_to is None and status in {
        TaskStatus.ASSIGNED,
        TaskStatus.IN_PROGRESS,
        TaskStatus.IN_REVIEW,
        TaskStatus.COMPLETED,
    }:
        assigned_to = "alice"
    return Task(
        id=task_id,
        title=title,
        description=description,
        type=TaskType.DEVELOPMENT,
        project=project,
        created_by=created_by,
        status=status,
        assigned_to=assigned_to,
    )


def make_approval(  # noqa: PLR0913
    *,
    approval_id: str = "approval-001",
    action_type: str = "code_merge",
    title: str = "Test approval",
    description: str = "A test approval item",
    requested_by: str = "agent-dev",
    risk_level: ApprovalRiskLevel = ApprovalRiskLevel.MEDIUM,
    status: ApprovalStatus = ApprovalStatus.PENDING,
    ttl_seconds: int | None = None,
    task_id: str | None = None,
) -> ApprovalItem:
    """Build an ApprovalItem with sensible defaults."""
    now = datetime.now(UTC)
    expires_at = None
    if ttl_seconds is not None:
        expires_at = now + timedelta(seconds=ttl_seconds)
    return ApprovalItem(
        id=approval_id,
        action_type=action_type,
        title=title,
        description=description,
        requested_by=requested_by,
        risk_level=risk_level,
        status=status,
        created_at=now,
        expires_at=expires_at,
        task_id=task_id,
    )
