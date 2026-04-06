"""Tests for agent mutation endpoints (POST, PATCH, DELETE agents)."""

from typing import Any

import pytest
from litestar.testing import TestClient

from tests.unit.api.conftest import make_auth_headers


@pytest.mark.unit
class TestCreateAgent:
    def test_create_agent_happy_path(
        self,
        test_client: TestClient[Any],
    ) -> None:
        # First create a department
        test_client.post(
            "/api/v1/departments",
            json={"name": "eng", "display_name": "Engineering"},
        )
        resp = test_client.post(
            "/api/v1/agents",
            json={
                "name": "alice",
                "role": "developer",
                "department": "eng",
                "level": "senior",
            },
        )
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["name"] == "alice"
        assert data["role"] == "developer"
        assert data["department"] == "eng"
        assert data["level"] == "senior"

    def test_create_agent_nonexistent_dept_422(
        self,
        test_client: TestClient[Any],
    ) -> None:
        resp = test_client.post(
            "/api/v1/agents",
            json={
                "name": "alice",
                "role": "developer",
                "department": "nonexistent",
                "level": "mid",
            },
        )
        assert resp.status_code == 422

    def test_create_agent_duplicate_name_409(
        self,
        test_client: TestClient[Any],
    ) -> None:
        test_client.post(
            "/api/v1/departments",
            json={"name": "eng", "display_name": "Engineering"},
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
        resp = test_client.post(
            "/api/v1/agents",
            json={
                "name": "alice",
                "role": "tester",
                "department": "eng",
                "level": "mid",
            },
        )
        assert resp.status_code == 409

    def test_create_agent_observer_denied(
        self,
        test_client: TestClient[Any],
    ) -> None:
        test_client.headers.update(make_auth_headers("observer"))
        resp = test_client.post(
            "/api/v1/agents",
            json={
                "name": "alice",
                "role": "dev",
                "department": "eng",
                "level": "mid",
            },
        )
        assert resp.status_code == 403


@pytest.mark.unit
class TestUpdateAgent:
    def test_update_agent_happy_path(
        self,
        test_client: TestClient[Any],
    ) -> None:
        test_client.post(
            "/api/v1/departments",
            json={"name": "eng", "display_name": "Engineering"},
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
        resp = test_client.patch(
            "/api/v1/agents/alice",
            json={"level": "senior"},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["level"] == "senior"

    def test_update_agent_not_found(
        self,
        test_client: TestClient[Any],
    ) -> None:
        resp = test_client.patch(
            "/api/v1/agents/nonexistent",
            json={"level": "senior"},
        )
        assert resp.status_code == 404


@pytest.mark.unit
class TestDeleteAgent:
    def test_delete_agent_happy_path(
        self,
        test_client: TestClient[Any],
    ) -> None:
        test_client.post(
            "/api/v1/departments",
            json={"name": "eng", "display_name": "Engineering"},
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
        resp = test_client.delete("/api/v1/agents/alice")
        assert resp.status_code == 204

    def test_delete_agent_not_found(
        self,
        test_client: TestClient[Any],
    ) -> None:
        resp = test_client.delete("/api/v1/agents/nonexistent")
        assert resp.status_code == 404
