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
from tests.unit.api.conftest import _TEST_JWT_SECRET
from tests.unit.api.fakes import FakePersistenceBackend


def _make_auth_service() -> AuthService:
    return AuthService(AuthConfig(jwt_secret=_TEST_JWT_SECRET))


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
    async def test_creates_user_on_empty_db(self) -> None:
        svc = _make_auth_service()
        persistence = FakePersistenceBackend()
        await persistence.connect()

        await ensure_system_user(persistence, svc)

        user = await persistence.users.get(SYSTEM_USER_ID)
        assert user is not None
        assert user.id == SYSTEM_USER_ID
        assert user.username == SYSTEM_USERNAME

    async def test_system_user_has_system_role(self) -> None:
        svc = _make_auth_service()
        persistence = FakePersistenceBackend()
        await persistence.connect()

        await ensure_system_user(persistence, svc)

        user = await persistence.users.get(SYSTEM_USER_ID)
        assert user is not None
        assert user.role == HumanRole.SYSTEM

    async def test_system_user_has_argon2id_hash(self) -> None:
        svc = _make_auth_service()
        persistence = FakePersistenceBackend()
        await persistence.connect()

        await ensure_system_user(persistence, svc)

        user = await persistence.users.get(SYSTEM_USER_ID)
        assert user is not None
        assert user.password_hash.startswith("$argon2id$")

    async def test_system_user_must_change_password_false(self) -> None:
        svc = _make_auth_service()
        persistence = FakePersistenceBackend()
        await persistence.connect()

        await ensure_system_user(persistence, svc)

        user = await persistence.users.get(SYSTEM_USER_ID)
        assert user is not None
        assert user.must_change_password is False

    async def test_idempotent(self) -> None:
        svc = _make_auth_service()
        persistence = FakePersistenceBackend()
        await persistence.connect()

        await ensure_system_user(persistence, svc)
        first = await persistence.users.get(SYSTEM_USER_ID)

        await ensure_system_user(persistence, svc)
        second = await persistence.users.get(SYSTEM_USER_ID)

        assert first is not None
        assert second is not None
        # Same object (not replaced) -- idempotent
        assert first.password_hash == second.password_hash

    async def test_excluded_from_count(self) -> None:
        svc = _make_auth_service()
        persistence = FakePersistenceBackend()
        await persistence.connect()

        await ensure_system_user(persistence, svc)

        # count() excludes system user
        assert await persistence.users.count() == 0

    async def test_excluded_from_list_users(self) -> None:
        svc = _make_auth_service()
        persistence = FakePersistenceBackend()
        await persistence.connect()

        await ensure_system_user(persistence, svc)

        # list_users() excludes system user
        users = await persistence.users.list_users()
        assert len(users) == 0
