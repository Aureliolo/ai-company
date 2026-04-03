"""Tests for AuthController endpoints."""

from typing import Any

import pytest
from litestar.testing import TestClient

from synthorg.api.guards import HumanRole
from tests.unit.api.conftest import _TEST_JWT_SECRET, make_auth_headers


@pytest.fixture
def bare_client(test_client: TestClient[Any]) -> TestClient[Any]:
    """Test client with no default Authorization header."""
    test_client.headers.pop("authorization", None)
    return test_client


@pytest.mark.unit
class TestSetup:
    def test_setup_creates_admin(self, bare_client: TestClient[Any]) -> None:
        app_state = bare_client.app.state["app_state"]
        app_state.persistence._users._users.clear()

        response = bare_client.post(
            "/api/v1/auth/setup",
            json={
                "username": "newadmin",
                "password": "super-secure-password-12",
            },
        )
        assert response.status_code == 201
        data = response.json()["data"]
        assert "token" in data
        assert data["must_change_password"] is False
        assert data["expires_in"] > 0

    def test_setup_409_when_users_exist(
        self,
        bare_client: TestClient[Any],
    ) -> None:
        # Re-seed a user so the check fails
        import uuid
        from datetime import UTC, datetime

        from synthorg.api.auth.models import User
        from synthorg.api.auth.service import AuthService
        from synthorg.api.guards import HumanRole

        app_state = bare_client.app.state["app_state"]
        svc: AuthService = app_state.auth_service
        now = datetime.now(UTC)
        user = User(
            id=str(uuid.uuid4()),
            username="existing",
            password_hash=svc.hash_password("test-password-12chars"),
            role=HumanRole.CEO,
            must_change_password=False,
            created_at=now,
            updated_at=now,
        )
        app_state.persistence._users._users[user.id] = user

        response = bare_client.post(
            "/api/v1/auth/setup",
            json={
                "username": "admin2",
                "password": "super-secure-password-12",
            },
        )
        assert response.status_code == 409

    def test_setup_short_password_rejected(self, bare_client: TestClient[Any]) -> None:
        app_state = bare_client.app.state["app_state"]
        app_state.persistence._users._users.clear()

        response = bare_client.post(
            "/api/v1/auth/setup",
            json={"username": "admin", "password": "short"},
        )
        assert response.status_code == 400


@pytest.mark.unit
class TestLogin:
    def test_login_valid_credentials(self, bare_client: TestClient[Any]) -> None:
        app_state = bare_client.app.state["app_state"]
        app_state.persistence._users._users.clear()

        bare_client.post(
            "/api/v1/auth/setup",
            json={
                "username": "loginuser",
                "password": "super-secure-password-12",
            },
        )

        response = bare_client.post(
            "/api/v1/auth/login",
            json={
                "username": "loginuser",
                "password": "super-secure-password-12",
            },
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert "token" in data
        assert data["expires_in"] > 0

    def test_login_wrong_password(self, bare_client: TestClient[Any]) -> None:
        response = bare_client.post(
            "/api/v1/auth/login",
            json={
                "username": "test-ceo",
                "password": "wrong-password-12345",
            },
        )
        assert response.status_code == 401

    def test_login_nonexistent_user(self, bare_client: TestClient[Any]) -> None:
        response = bare_client.post(
            "/api/v1/auth/login",
            json={
                "username": "nonexistent",
                "password": "any-password-12345",
            },
        )
        assert response.status_code == 401


@pytest.mark.unit
class TestChangePassword:
    def test_change_password_success(self, bare_client: TestClient[Any]) -> None:
        app_state = bare_client.app.state["app_state"]
        app_state.persistence._users._users.clear()

        setup_resp = bare_client.post(
            "/api/v1/auth/setup",
            json={
                "username": "changepw",
                "password": "old-password-12chars",
            },
        )
        token = setup_resp.json()["data"]["token"]

        response = bare_client.post(
            "/api/v1/auth/change-password",
            json={
                "current_password": "old-password-12chars",
                "new_password": "new-password-12chars",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["must_change_password"] is False

    def test_change_password_wrong_current(self, test_client: TestClient[Any]) -> None:
        response = test_client.post(
            "/api/v1/auth/change-password",
            json={
                "current_password": "wrong-current-pw-12",
                "new_password": "new-password-12chars",
            },
            headers=make_auth_headers("ceo"),
        )
        assert response.status_code == 401

    def test_change_password_requires_auth(self, bare_client: TestClient[Any]) -> None:
        response = bare_client.post(
            "/api/v1/auth/change-password",
            json={
                "current_password": "old-password-12chars",
                "new_password": "new-password-12chars",
            },
        )
        assert response.status_code == 401

    def test_change_password_short_new_password(
        self,
        bare_client: TestClient[Any],
    ) -> None:
        app_state = bare_client.app.state["app_state"]
        app_state.persistence._users._users.clear()

        setup_resp = bare_client.post(
            "/api/v1/auth/setup",
            json={
                "username": "shortpw",
                "password": "old-password-12chars",
            },
        )
        token = setup_resp.json()["data"]["token"]

        response = bare_client.post(
            "/api/v1/auth/change-password",
            json={
                "current_password": "old-password-12chars",
                "new_password": "short",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 400


@pytest.mark.unit
class TestMe:
    def test_me_returns_user_info(self, test_client: TestClient[Any]) -> None:
        response = test_client.get(
            "/api/v1/auth/me",
            headers=make_auth_headers("ceo"),
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["username"] == "test-ceo"
        assert data["role"] == "ceo"
        assert data["must_change_password"] is False

    def test_me_requires_auth(self, bare_client: TestClient[Any]) -> None:
        response = bare_client.get("/api/v1/auth/me")
        assert response.status_code == 401


@pytest.mark.unit
class TestRequirePasswordChanged:
    def test_blocks_user_with_must_change_password(self) -> None:
        """Guard raises PermissionDeniedException for flagged users."""
        from unittest.mock import MagicMock

        from litestar.exceptions import PermissionDeniedException

        from synthorg.api.auth.controller import require_password_changed
        from synthorg.api.auth.models import AuthenticatedUser, AuthMethod

        user = AuthenticatedUser(
            user_id="u1",
            username="admin",
            role=HumanRole.CEO,
            auth_method=AuthMethod.JWT,
            must_change_password=True,
        )
        connection = MagicMock()
        connection.scope = {"user": user}
        connection.url.path = "/api/v1/health"

        with pytest.raises(PermissionDeniedException):
            require_password_changed(connection, None)

    def test_allows_user_without_flag(self) -> None:
        """Guard passes when must_change_password is False."""
        from unittest.mock import MagicMock

        from synthorg.api.auth.controller import require_password_changed
        from synthorg.api.auth.models import AuthenticatedUser, AuthMethod

        user = AuthenticatedUser(
            user_id="u1",
            username="admin",
            role=HumanRole.CEO,
            auth_method=AuthMethod.JWT,
            must_change_password=False,
        )
        connection = MagicMock()
        connection.scope = {"user": user}
        connection.url.path = "/api/v1/health"

        # Should not raise
        require_password_changed(connection, None)

    def test_allows_when_no_user_in_scope(self) -> None:
        """Guard passes when no user is in scope (pre-auth)."""
        from unittest.mock import MagicMock

        from synthorg.api.auth.controller import require_password_changed

        connection = MagicMock()
        connection.scope = {}
        connection.url.path = "/api/v1/health"

        # Should not raise
        require_password_changed(connection, None)

    @pytest.mark.parametrize(
        "path",
        [
            pytest.param("/api/v1/auth/change-password", id="change-password"),
            pytest.param("/api/v1/auth/me", id="me"),
        ],
    )
    def test_exempts_paths_for_must_change_password_users(
        self,
        path: str,
    ) -> None:
        """Guard allows must_change_password users on exempt paths."""
        from unittest.mock import MagicMock

        from synthorg.api.auth.controller import require_password_changed
        from synthorg.api.auth.models import AuthenticatedUser, AuthMethod

        user = AuthenticatedUser(
            user_id="u1",
            username="admin",
            role=HumanRole.CEO,
            auth_method=AuthMethod.JWT,
            must_change_password=True,
        )
        connection = MagicMock()
        connection.scope = {"user": user}
        connection.url.path = path

        # Should not raise -- exempt path
        require_password_changed(connection, None)

    def test_rejects_unknown_user_type(self) -> None:
        """Guard raises PermissionDeniedException for non-AuthenticatedUser."""
        from unittest.mock import MagicMock

        from litestar.exceptions import PermissionDeniedException

        from synthorg.api.auth.controller import require_password_changed

        connection = MagicMock()
        connection.scope = {"user": "not-an-auth-user"}
        connection.url.path = "/api/v1/health"

        with pytest.raises(PermissionDeniedException):
            require_password_changed(connection, None)


@pytest.mark.unit
class TestWsTicket:
    def test_ws_ticket_returns_ticket_and_expires_in(
        self,
        test_client: TestClient[Any],
    ) -> None:
        response = test_client.post("/api/v1/auth/ws-ticket")
        assert response.status_code == 200
        data = response.json()["data"]
        assert "ticket" in data
        assert isinstance(data["ticket"], str)
        assert len(data["ticket"]) > 0
        assert data["expires_in"] == 30

    def test_ws_ticket_requires_auth(
        self,
        bare_client: TestClient[Any],
    ) -> None:
        response = bare_client.post("/api/v1/auth/ws-ticket")
        assert response.status_code == 401

    def test_ws_ticket_with_observer_role(
        self,
        test_client: TestClient[Any],
    ) -> None:
        """All roles should be able to get a WS ticket."""
        response = test_client.post(
            "/api/v1/auth/ws-ticket",
            headers=make_auth_headers("observer"),
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert "ticket" in data

    def test_ws_ticket_is_consumable(
        self,
        test_client: TestClient[Any],
    ) -> None:
        """The returned ticket can be consumed by the ticket store."""
        response = test_client.post("/api/v1/auth/ws-ticket")
        data = response.json()["data"]
        ticket = data["ticket"]

        app_state = test_client.app.state["app_state"]
        user = app_state.ticket_store.validate_and_consume(ticket)
        assert user is not None
        assert user.auth_method.value == "ws_ticket"

        # Single-use: second consume fails
        assert app_state.ticket_store.validate_and_consume(ticket) is None


@pytest.mark.unit
class TestSystemUserBlocking:
    """Verify the system user cannot log in or change its password."""

    def test_login_rejects_system_user(
        self,
        bare_client: TestClient[Any],
    ) -> None:
        """System user login returns 401 (same as invalid credentials)."""
        from datetime import UTC, datetime

        from synthorg.api.auth.models import User
        from synthorg.api.auth.system_user import (
            SYSTEM_USER_ID,
            SYSTEM_USERNAME,
        )

        # Seed a system user via the public save() API
        app_state = bare_client.app.state["app_state"]
        now = datetime.now(UTC)
        svc = app_state.auth_service
        system_user = User(
            id=SYSTEM_USER_ID,
            username=SYSTEM_USERNAME,
            password_hash=svc.hash_password("irrelevant-password-12"),
            role=HumanRole.SYSTEM,
            must_change_password=False,
            created_at=now,
            updated_at=now,
        )
        # Use internal dict because save() is async and this is a sync test
        app_state.persistence._users._users[SYSTEM_USER_ID] = system_user

        response = bare_client.post(
            "/api/v1/auth/login",
            json={
                "username": "system",
                "password": "irrelevant-password-12",
            },
        )
        assert response.status_code == 401

    def test_change_password_rejects_system_user(
        self,
        bare_client: TestClient[Any],
    ) -> None:
        """System user cannot change its password (403)."""
        from datetime import UTC, datetime, timedelta

        import jwt as pyjwt

        from synthorg.api.auth.models import User
        from synthorg.api.auth.system_user import (
            SYSTEM_USER_ID,
            SYSTEM_USERNAME,
        )

        # Explicitly seed the system user so the test is self-contained
        app_state = bare_client.app.state["app_state"]
        now = datetime.now(UTC)
        svc = app_state.auth_service
        system_user = User(
            id=SYSTEM_USER_ID,
            username=SYSTEM_USERNAME,
            password_hash=svc.hash_password("irrelevant-password-12"),
            role=HumanRole.SYSTEM,
            must_change_password=False,
            created_at=now,
            updated_at=now,
        )
        app_state.persistence._users._users[SYSTEM_USER_ID] = system_user

        # Build a CLI-style JWT with iss + aud (required by middleware)
        token = pyjwt.encode(
            {
                "sub": SYSTEM_USER_ID,
                "iss": "synthorg-cli",
                "aud": "synthorg-backend",
                "jti": "sys-change-pwd",
                "iat": now,
                "exp": now + timedelta(seconds=60),
            },
            _TEST_JWT_SECRET,
            algorithm="HS256",
        )

        response = bare_client.post(
            "/api/v1/auth/change-password",
            json={
                "current_password": "any-password-12chars",
                "new_password": "new-password-12chars",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403

    def test_setup_succeeds_with_system_user_present(
        self,
        bare_client: TestClient[Any],
    ) -> None:
        """Setup endpoint returns 201 when only the system user exists."""
        from datetime import UTC, datetime

        from synthorg.api.auth.models import User
        from synthorg.api.auth.system_user import (
            SYSTEM_USER_ID,
            SYSTEM_USERNAME,
        )

        app_state = bare_client.app.state["app_state"]
        # Clear all users, then add only the system user
        app_state.persistence._users._users.clear()
        now = datetime.now(UTC)
        system_user = User(
            id=SYSTEM_USER_ID,
            username=SYSTEM_USERNAME,
            password_hash="$argon2id$v=19$m=65536,t=3,p=4$fake$hash",
            role=HumanRole.SYSTEM,
            must_change_password=False,
            created_at=now,
            updated_at=now,
        )
        app_state.persistence._users._users[SYSTEM_USER_ID] = system_user

        response = bare_client.post(
            "/api/v1/auth/setup",
            json={
                "username": "newadmin",
                "password": "super-secure-password-12",
            },
        )
        assert response.status_code == 201

    def test_setup_rejects_reserved_system_username(
        self,
        bare_client: TestClient[Any],
    ) -> None:
        """Setup rejects the reserved 'system' username with 409."""
        app_state = bare_client.app.state["app_state"]
        app_state.persistence._users._users.clear()

        response = bare_client.post(
            "/api/v1/auth/setup",
            json={
                "username": "system",
                "password": "super-secure-password-12",
            },
        )
        assert response.status_code == 409

    def test_setup_succeeds_with_non_ceo_human_users_present(
        self,
        bare_client: TestClient[Any],
    ) -> None:
        """Setup succeeds when only non-CEO human users exist."""
        from datetime import UTC, datetime

        from synthorg.api.auth.models import User

        app_state = bare_client.app.state["app_state"]
        app_state.persistence._users._users.clear()
        now = datetime.now(UTC)
        observer = User(
            id="observer-001",
            username="watcher",
            password_hash="$argon2id$v=19$m=65536,t=3,p=4$fake$hash",
            role=HumanRole.OBSERVER,
            must_change_password=False,
            created_at=now,
            updated_at=now,
        )
        app_state.persistence._users._users["observer-001"] = observer

        response = bare_client.post(
            "/api/v1/auth/setup",
            json={
                "username": "firstadmin",
                "password": "super-secure-password-12",
            },
        )
        assert response.status_code == 201
