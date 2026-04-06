"""Tests for department mutation endpoints (POST, PATCH, DELETE departments)."""

from typing import Any

import pytest
from litestar.testing import TestClient

from tests.unit.api.conftest import make_auth_headers


@pytest.mark.unit
class TestCreateDepartment:
    def test_create_department_happy_path(
        self,
        test_client: TestClient[Any],
    ) -> None:
        resp = test_client.post(
            "/api/v1/departments",
            json={"name": "engineering"},
        )
        assert resp.status_code == 201
        assert resp.json()["data"]["name"] == "engineering"

    def test_create_department_duplicate_409(
        self,
        test_client: TestClient[Any],
    ) -> None:
        test_client.post(
            "/api/v1/departments",
            json={"name": "engineering"},
        )
        resp = test_client.post(
            "/api/v1/departments",
            json={"name": "engineering"},
        )
        assert resp.status_code == 409

    def test_create_department_observer_denied(
        self,
        test_client: TestClient[Any],
    ) -> None:
        test_client.headers.update(make_auth_headers("observer"))
        resp = test_client.post(
            "/api/v1/departments",
            json={"name": "eng"},
        )
        assert resp.status_code == 403


@pytest.mark.unit
class TestUpdateDepartment:
    def test_update_department_happy_path(
        self,
        test_client: TestClient[Any],
    ) -> None:
        test_client.post(
            "/api/v1/departments",
            json={"name": "eng"},
        )
        resp = test_client.patch(
            "/api/v1/departments/eng",
            json={"budget_percent": 40.0},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["budget_percent"] == 40.0

    def test_update_department_not_found(
        self,
        test_client: TestClient[Any],
    ) -> None:
        resp = test_client.patch(
            "/api/v1/departments/nonexistent",
            json={"budget_percent": 10.0},
        )
        assert resp.status_code == 404


@pytest.mark.unit
class TestDeleteDepartment:
    def test_delete_department_happy_path(
        self,
        test_client: TestClient[Any],
    ) -> None:
        test_client.post(
            "/api/v1/departments",
            json={"name": "eng"},
        )
        resp = test_client.delete("/api/v1/departments/eng")
        assert resp.status_code == 204

    def test_delete_department_not_found(
        self,
        test_client: TestClient[Any],
    ) -> None:
        resp = test_client.delete("/api/v1/departments/nonexistent")
        assert resp.status_code == 404

    def test_delete_department_with_agents_409(
        self,
        test_client: TestClient[Any],
    ) -> None:
        test_client.post(
            "/api/v1/departments",
            json={"name": "eng"},
        )
        test_client.post(
            "/api/v1/agents",
            json={
                "name": "alice",
                "role": "developer",
                "department": "eng",
                "level": "mid",
            },
        )
        resp = test_client.delete("/api/v1/departments/eng")
        assert resp.status_code == 409


@pytest.mark.unit
class TestReorderAgents:
    def test_reorder_agents_happy_path(
        self,
        test_client: TestClient[Any],
    ) -> None:
        test_client.post(
            "/api/v1/departments",
            json={"name": "eng"},
        )
        test_client.post(
            "/api/v1/agents",
            json={
                "name": "alice",
                "role": "dev",
                "department": "eng",
                "level": "mid",
            },
        )
        test_client.post(
            "/api/v1/agents",
            json={
                "name": "bob",
                "role": "dev",
                "department": "eng",
                "level": "mid",
            },
        )
        resp = test_client.post(
            "/api/v1/departments/eng/reorder-agents",
            json={"agent_names": ["bob", "alice"]},
        )
        assert resp.status_code == 201
        names = [a["name"] for a in resp.json()["data"]]
        assert names == ["bob", "alice"]
