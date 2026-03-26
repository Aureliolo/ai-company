"""Tests for user management controller (CEO-only CRUD)."""

import uuid
from typing import Any

import pytest
from litestar.testing import TestClient

from tests.unit.api.conftest import make_auth_headers

# Must match the ID pattern in conftest._seed_test_users
_SYSTEM_USER_ID = str(uuid.uuid5(uuid.NAMESPACE_DNS, "test-system"))

_BASE = "/api/v1/users"
_CEO_HEADERS = make_auth_headers("ceo")


def _create_payload(
    **overrides: Any,
) -> dict[str, Any]:
    defaults: dict[str, Any] = {
        "username": "new-user",
        "password": "secure-password-12chars",
        "role": "manager",
    }
    defaults.update(overrides)
    return defaults


@pytest.mark.unit
class TestCreateUser:
    def test_create_manager(self, test_client: TestClient[Any]) -> None:
        resp = test_client.post(
            _BASE,
            json=_create_payload(),
            headers=_CEO_HEADERS,
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["success"] is True
        data = body["data"]
        assert data["username"] == "new-user"
        assert data["role"] == "manager"
        assert data["must_change_password"] is True
        assert "password_hash" not in data

    def test_create_board_member(self, test_client: TestClient[Any]) -> None:
        resp = test_client.post(
            _BASE,
            json=_create_payload(
                username="board-user",
                role="board_member",
            ),
            headers=_CEO_HEADERS,
        )
        assert resp.status_code == 201
        assert resp.json()["data"]["role"] == "board_member"

    def test_create_pair_programmer(
        self,
        test_client: TestClient[Any],
    ) -> None:
        resp = test_client.post(
            _BASE,
            json=_create_payload(
                username="pp-user",
                role="pair_programmer",
            ),
            headers=_CEO_HEADERS,
        )
        assert resp.status_code == 201
        assert resp.json()["data"]["role"] == "pair_programmer"

    def test_create_observer(self, test_client: TestClient[Any]) -> None:
        resp = test_client.post(
            _BASE,
            json=_create_payload(username="obs-user", role="observer"),
            headers=_CEO_HEADERS,
        )
        assert resp.status_code == 201
        assert resp.json()["data"]["role"] == "observer"

    def test_create_second_ceo_rejected(
        self,
        test_client: TestClient[Any],
    ) -> None:
        resp = test_client.post(
            _BASE,
            json=_create_payload(username="ceo2", role="ceo"),
            headers=_CEO_HEADERS,
        )
        assert resp.status_code == 409

    def test_create_system_role_rejected(
        self,
        test_client: TestClient[Any],
    ) -> None:
        resp = test_client.post(
            _BASE,
            json=_create_payload(username="sys", role="system"),
            headers=_CEO_HEADERS,
        )
        assert resp.status_code == 422

    def test_create_duplicate_username_rejected(
        self,
        test_client: TestClient[Any],
    ) -> None:
        test_client.post(
            _BASE,
            json=_create_payload(username="dup-user"),
            headers=_CEO_HEADERS,
        )
        resp = test_client.post(
            _BASE,
            json=_create_payload(username="dup-user"),
            headers=_CEO_HEADERS,
        )
        assert resp.status_code == 409

    def test_create_short_password_rejected(
        self,
        test_client: TestClient[Any],
    ) -> None:
        resp = test_client.post(
            _BASE,
            json=_create_payload(password="short"),
            headers=_CEO_HEADERS,
        )
        assert resp.status_code == 422

    @pytest.mark.parametrize(
        "role",
        ["manager", "board_member", "pair_programmer", "observer"],
    )
    def test_non_ceo_blocked(
        self,
        test_client: TestClient[Any],
        role: str,
    ) -> None:
        resp = test_client.post(
            _BASE,
            json=_create_payload(),
            headers=make_auth_headers(role),
        )
        assert resp.status_code == 403


@pytest.mark.unit
class TestListUsers:
    def test_list_returns_seeded_users(
        self,
        test_client: TestClient[Any],
    ) -> None:
        resp = test_client.get(_BASE, headers=_CEO_HEADERS)
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        # At least the seeded non-system users exist
        assert len(body["data"]) >= 1

    def test_list_blocked_for_observer(
        self,
        test_client: TestClient[Any],
    ) -> None:
        resp = test_client.get(
            _BASE,
            headers=make_auth_headers("observer"),
        )
        assert resp.status_code == 403


@pytest.mark.unit
class TestGetUser:
    def test_get_existing_user(
        self,
        test_client: TestClient[Any],
    ) -> None:
        # Create a user first
        create_resp = test_client.post(
            _BASE,
            json=_create_payload(username="get-test"),
            headers=_CEO_HEADERS,
        )
        user_id = create_resp.json()["data"]["id"]

        resp = test_client.get(
            f"{_BASE}/{user_id}",
            headers=_CEO_HEADERS,
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["username"] == "get-test"

    def test_get_nonexistent_returns_404(
        self,
        test_client: TestClient[Any],
    ) -> None:
        resp = test_client.get(
            f"{_BASE}/nonexistent-id",
            headers=_CEO_HEADERS,
        )
        assert resp.status_code == 404


@pytest.mark.unit
class TestUpdateUserRole:
    def test_update_role(self, test_client: TestClient[Any]) -> None:
        create_resp = test_client.post(
            _BASE,
            json=_create_payload(username="update-test"),
            headers=_CEO_HEADERS,
        )
        user_id = create_resp.json()["data"]["id"]

        resp = test_client.patch(
            f"{_BASE}/{user_id}",
            json={"role": "observer"},
            headers=_CEO_HEADERS,
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["role"] == "observer"

    def test_update_to_system_rejected(
        self,
        test_client: TestClient[Any],
    ) -> None:
        create_resp = test_client.post(
            _BASE,
            json=_create_payload(username="sys-update"),
            headers=_CEO_HEADERS,
        )
        user_id = create_resp.json()["data"]["id"]

        resp = test_client.patch(
            f"{_BASE}/{user_id}",
            json={"role": "system"},
            headers=_CEO_HEADERS,
        )
        assert resp.status_code == 422

    def test_update_nonexistent_returns_404(
        self,
        test_client: TestClient[Any],
    ) -> None:
        resp = test_client.patch(
            f"{_BASE}/nonexistent-id",
            json={"role": "observer"},
            headers=_CEO_HEADERS,
        )
        assert resp.status_code == 404

    def test_demote_only_ceo_rejected(
        self,
        test_client: TestClient[Any],
    ) -> None:
        # The seeded CEO is the only one -- changing role must fail.
        list_resp = test_client.get(_BASE, headers=_CEO_HEADERS)
        ceo_users = [u for u in list_resp.json()["data"] if u["role"] == "ceo"]
        assert len(ceo_users) == 1
        ceo_id = ceo_users[0]["id"]

        resp = test_client.patch(
            f"{_BASE}/{ceo_id}",
            json={"role": "manager"},
            headers=_CEO_HEADERS,
        )
        assert resp.status_code == 409

    def test_promote_to_second_ceo_rejected(
        self,
        test_client: TestClient[Any],
    ) -> None:
        create_resp = test_client.post(
            _BASE,
            json=_create_payload(username="promote-test"),
            headers=_CEO_HEADERS,
        )
        user_id = create_resp.json()["data"]["id"]

        resp = test_client.patch(
            f"{_BASE}/{user_id}",
            json={"role": "ceo"},
            headers=_CEO_HEADERS,
        )
        assert resp.status_code == 409


@pytest.mark.unit
class TestDeleteUser:
    def test_delete_user(self, test_client: TestClient[Any]) -> None:
        create_resp = test_client.post(
            _BASE,
            json=_create_payload(username="delete-test"),
            headers=_CEO_HEADERS,
        )
        user_id = create_resp.json()["data"]["id"]

        resp = test_client.delete(
            f"{_BASE}/{user_id}",
            headers=_CEO_HEADERS,
        )
        assert resp.status_code == 204

        # Verify deleted
        get_resp = test_client.get(
            f"{_BASE}/{user_id}",
            headers=_CEO_HEADERS,
        )
        assert get_resp.status_code == 404

    def test_delete_nonexistent_returns_404(
        self,
        test_client: TestClient[Any],
    ) -> None:
        resp = test_client.delete(
            f"{_BASE}/nonexistent-id",
            headers=_CEO_HEADERS,
        )
        assert resp.status_code == 404

    def test_delete_system_user_rejected(
        self,
        test_client: TestClient[Any],
    ) -> None:
        resp = test_client.delete(
            f"{_BASE}/{_SYSTEM_USER_ID}",
            headers=_CEO_HEADERS,
        )
        assert resp.status_code == 409

    def test_delete_ceo_rejected(
        self,
        test_client: TestClient[Any],
    ) -> None:
        # The seeded CEO user -- find its ID from list
        list_resp = test_client.get(_BASE, headers=_CEO_HEADERS)
        ceo_users = [u for u in list_resp.json()["data"] if u["role"] == "ceo"]
        assert len(ceo_users) > 0
        ceo_id = ceo_users[0]["id"]

        resp = test_client.delete(
            f"{_BASE}/{ceo_id}",
            headers=_CEO_HEADERS,
        )
        assert resp.status_code == 409
