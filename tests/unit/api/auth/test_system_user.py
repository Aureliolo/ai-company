"""Tests for the system user module."""

import pytest

from synthorg.api.auth.config import AuthConfig
from synthorg.api.auth.service import AuthService
from synthorg.api.auth.system_user import (
    SYSTEM_USER_ID,
    SYSTEM_USERNAME,
    ensure_system_user,
    is_system_user,
)
from synthorg.api.guards import HumanRole
from synthorg.persistence.errors import QueryError
from tests.unit.api.conftest import _TEST_JWT_SECRET
from tests.unit.api.fakes import FakePersistenceBackend


def _make_auth_service() -> AuthService:
    return AuthService(AuthConfig(jwt_secret=_TEST_JWT_SECRET))


@pytest.fixture
def auth_svc() -> AuthService:
    return _make_auth_service()


@pytest.fixture
async def fake_persistence() -> FakePersistenceBackend:
    backend = FakePersistenceBackend()
    await backend.connect()
    return backend


@pytest.mark.unit
class TestIsSystemUser:
    def test_true_for_system_id(self) -> None:
        assert is_system_user(SYSTEM_USER_ID) is True

    def test_false_for_other_id(self) -> None:
        assert is_system_user("some-other-id") is False

    def test_false_for_empty(self) -> None:
        assert is_system_user("") is False


@pytest.mark.unit
class TestEnsureSystemUser:
    async def test_creates_user_on_empty_db(
        self, auth_svc: AuthService, fake_persistence: FakePersistenceBackend
    ) -> None:
        await ensure_system_user(fake_persistence, auth_svc)

        user = await fake_persistence.users.get(SYSTEM_USER_ID)
        assert user is not None
        assert user.id == SYSTEM_USER_ID
        assert user.username == SYSTEM_USERNAME

    async def test_system_user_has_system_role(
        self, auth_svc: AuthService, fake_persistence: FakePersistenceBackend
    ) -> None:
        await ensure_system_user(fake_persistence, auth_svc)

        user = await fake_persistence.users.get(SYSTEM_USER_ID)
        assert user is not None
        assert user.role == HumanRole.SYSTEM

    async def test_system_user_has_argon2id_hash(
        self, auth_svc: AuthService, fake_persistence: FakePersistenceBackend
    ) -> None:
        await ensure_system_user(fake_persistence, auth_svc)

        user = await fake_persistence.users.get(SYSTEM_USER_ID)
        assert user is not None
        assert user.password_hash.startswith("$argon2id$")

    async def test_system_user_must_change_password_false(
        self, auth_svc: AuthService, fake_persistence: FakePersistenceBackend
    ) -> None:
        await ensure_system_user(fake_persistence, auth_svc)

        user = await fake_persistence.users.get(SYSTEM_USER_ID)
        assert user is not None
        assert user.must_change_password is False

    async def test_idempotent(
        self, auth_svc: AuthService, fake_persistence: FakePersistenceBackend
    ) -> None:
        await ensure_system_user(fake_persistence, auth_svc)
        first = await fake_persistence.users.get(SYSTEM_USER_ID)

        await ensure_system_user(fake_persistence, auth_svc)
        second = await fake_persistence.users.get(SYSTEM_USER_ID)

        assert first is not None
        assert second is not None
        # Same object (not replaced) -- idempotent
        assert first.password_hash == second.password_hash

    async def test_excluded_from_count(
        self, auth_svc: AuthService, fake_persistence: FakePersistenceBackend
    ) -> None:
        await ensure_system_user(fake_persistence, auth_svc)

        # count() excludes system user
        assert await fake_persistence.users.count() == 0

    async def test_excluded_from_list_users(
        self, auth_svc: AuthService, fake_persistence: FakePersistenceBackend
    ) -> None:
        await ensure_system_user(fake_persistence, auth_svc)

        # list_users() excludes system user
        users = await fake_persistence.users.list_users()
        assert len(users) == 0

    async def test_persistence_error_propagates(
        self, auth_svc: AuthService, fake_persistence: FakePersistenceBackend
    ) -> None:
        """Errors from persistence.users.save propagate to the caller."""
        original_save = fake_persistence.users.save

        async def _failing_save(user: object) -> None:
            msg = "simulated DB failure"
            raise QueryError(msg)

        fake_persistence.users.save = _failing_save  # type: ignore[assignment]
        with pytest.raises(QueryError, match="simulated DB failure"):
            await ensure_system_user(fake_persistence, auth_svc)

        fake_persistence.users.save = original_save  # type: ignore[assignment]
