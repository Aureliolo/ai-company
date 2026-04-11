"""Tests for atomic user operations after _CEO_LOCK removal.

Verifies that the user controller correctly handles DB constraint
violations (unique index, triggers) without relying on an in-process
asyncio.Lock.  The DB is the sole enforcement mechanism; the fake
backend simulates the same constraints.
"""

import uuid
from typing import Any

import pytest
from litestar.testing import TestClient

from tests.unit.api.conftest import make_auth_headers

_BASE = "/api/v1/users"
_CEO_HEADERS = make_auth_headers("ceo")


def _create_payload(**overrides: Any) -> dict[str, Any]:
    defaults: dict[str, Any] = {
        "username": "new-user",
        "password": "secure-password-12chars",
        "role": "manager",
    }
    return {**defaults, **overrides}


# ── Module-level lock must not exist ──────────────────────────


@pytest.mark.unit
class TestNoModuleLevelLock:
    """Verify the asyncio.Lock was actually removed."""

    def test_ceo_lock_removed(self) -> None:
        from synthorg.api.controllers import users

        assert not hasattr(users, "_CEO_LOCK"), (
            "_CEO_LOCK still exists -- it should be removed"
        )

    def test_validate_ceo_create_removed(self) -> None:
        from synthorg.api.controllers import users

        assert not hasattr(users, "_validate_ceo_create"), (
            "_validate_ceo_create should be removed"
        )

    def test_validate_role_change_removed(self) -> None:
        from synthorg.api.controllers import users

        assert not hasattr(users, "_validate_role_change"), (
            "_validate_role_change should be removed"
        )


# ── CEO creation constraint handling ──────────────────────────


@pytest.mark.unit
class TestCEOCreationConstraint:
    """Controller maps QueryError from save() to ConflictError (409)."""

    def test_second_ceo_returns_409(
        self,
        test_client: TestClient[Any],
    ) -> None:
        """Creating a second CEO gets 409 from DB constraint."""
        resp = test_client.post(
            _BASE,
            json=_create_payload(username="ceo2", role="ceo"),
            headers=_CEO_HEADERS,
        )
        assert resp.status_code == 409

    def test_duplicate_username_returns_409(
        self,
        test_client: TestClient[Any],
    ) -> None:
        """Duplicate username gets 409 from UNIQUE constraint."""
        test_client.post(
            _BASE,
            json=_create_payload(username="unique-user", role="manager"),
            headers=_CEO_HEADERS,
        )
        resp = test_client.post(
            _BASE,
            json=_create_payload(username="unique-user", role="observer"),
            headers=_CEO_HEADERS,
        )
        assert resp.status_code == 409


# ── Role change constraint handling ───────────────────────────


@pytest.mark.unit
class TestRoleChangeConstraint:
    """Controller maps role-change constraint violations to 409."""

    def test_update_to_ceo_when_ceo_exists_returns_409(
        self,
        test_client: TestClient[Any],
    ) -> None:
        """Promoting to CEO when one exists gets 409."""
        resp = test_client.post(
            _BASE,
            json=_create_payload(username="promote-target", role="manager"),
            headers=_CEO_HEADERS,
        )
        assert resp.status_code == 201
        user_id = resp.json()["data"]["id"]

        resp = test_client.patch(
            f"{_BASE}/{user_id}",
            json={"role": "ceo"},
            headers=_CEO_HEADERS,
        )
        assert resp.status_code == 409

    def test_demote_last_ceo_returns_409(
        self,
        test_client: TestClient[Any],
    ) -> None:
        """Demoting the only CEO gets 409 from DB trigger.

        The fake backend enforces the last-CEO constraint.
        """
        ceo_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, "test-ceo"))

        resp = test_client.patch(
            f"{_BASE}/{ceo_id}",
            json={"role": "manager"},
            headers=_CEO_HEADERS,
        )
        assert resp.status_code == 409
        assert "CEO" in resp.json().get("error", "")


# ── Owner revocation constraint handling ──────────────────────


@pytest.mark.unit
class TestOwnerRevocationConstraint:
    """Controller maps last-owner trigger violation to 409."""

    def test_revoke_last_owner_returns_409(
        self,
        test_client: TestClient[Any],
    ) -> None:
        """Revoking the last owner gets 409 from DB trigger.

        The fake backend enforces the last-owner constraint.
        The test_client fixture auto-promotes the first CEO user
        to owner on startup, so we just need to revoke that.
        """
        ceo_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, "test-ceo"))

        resp = test_client.delete(
            f"{_BASE}/{ceo_id}/org-roles/owner",
            headers=_CEO_HEADERS,
        )
        assert resp.status_code == 409

    async def test_delete_user_maps_last_owner_to_409(self) -> None:
        """delete_user maps LAST_OWNER_TRIGGER constraint to ConflictError.

        Calls the handler directly rather than going through TestClient
        because consecutive TestClient requests on Windows + Python 3.14
        hit an event-loop cleanup race that hangs the test.
        """
        from types import SimpleNamespace
        from unittest.mock import AsyncMock

        from synthorg.api.controllers.users import UserController
        from synthorg.api.errors import ConflictError
        from synthorg.api.guards import HumanRole
        from synthorg.persistence.constraint_tokens import LAST_OWNER_TRIGGER
        from synthorg.persistence.errors import ConstraintViolationError

        # Build a minimal fake user for the 404 check and role guards.
        target_user = SimpleNamespace(
            id="target-user-id",
            role=HumanRole.MANAGER,
        )

        fake_users_repo = AsyncMock()
        fake_users_repo.get = AsyncMock(return_value=target_user)
        fake_users_repo.delete = AsyncMock(
            side_effect=ConstraintViolationError(
                "Cannot delete user",
                constraint=LAST_OWNER_TRIGGER,
            ),
        )
        fake_persistence = SimpleNamespace(users=fake_users_repo)
        app_state = SimpleNamespace(persistence=fake_persistence)
        state = SimpleNamespace(app_state=app_state)
        request = SimpleNamespace(
            scope={
                "user": SimpleNamespace(user_id="admin-user-id"),
            },
        )

        # Litestar wraps the decorated method; call the underlying fn.
        delete_fn = UserController.delete_user.fn
        controller = object.__new__(UserController)
        with pytest.raises(ConflictError, match="Cannot delete the last owner"):
            await delete_fn(
                controller,
                state=state,
                user_id="target-user-id",
                request=request,
            )
        fake_users_repo.delete.assert_awaited_once_with("target-user-id")
