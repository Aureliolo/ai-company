"""Tests for artifact controller."""

from typing import Any

import pytest
from litestar.testing import TestClient

from tests.unit.api.conftest import make_auth_headers


@pytest.mark.unit
class TestArtifactController:
    def test_list_artifacts_empty(self, test_client: TestClient[Any]) -> None:
        resp = test_client.get("/api/v1/artifacts")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"] == []
        assert body["pagination"]["total"] == 0

    def test_get_artifact_not_found(self, test_client: TestClient[Any]) -> None:
        resp = test_client.get("/api/v1/artifacts/nonexistent")
        assert resp.status_code == 404
        body = resp.json()
        assert body["success"] is False
        assert "not found" in body["error"].lower()

    def test_create_and_get_artifact(self, test_client: TestClient[Any]) -> None:
        create_resp = test_client.post(
            "/api/v1/artifacts",
            json={
                "type": "code",
                "path": "src/auth/login.py",
                "task_id": "task-123",
                "created_by": "agent-1",
                "description": "Login endpoint",
            },
            headers=make_auth_headers("ceo"),
        )
        assert create_resp.status_code == 201
        created = create_resp.json()
        assert created["success"] is True
        artifact_id = created["data"]["id"]
        assert artifact_id.startswith("artifact-")
        assert created["data"]["type"] == "code"
        assert created["data"]["path"] == "src/auth/login.py"

        get_resp = test_client.get(f"/api/v1/artifacts/{artifact_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["data"]["id"] == artifact_id

    def test_list_artifacts_after_create(self, test_client: TestClient[Any]) -> None:
        test_client.post(
            "/api/v1/artifacts",
            json={
                "type": "code",
                "path": "src/a.py",
                "task_id": "task-1",
                "created_by": "agent-1",
            },
            headers=make_auth_headers("ceo"),
        )
        test_client.post(
            "/api/v1/artifacts",
            json={
                "type": "tests",
                "path": "tests/a.py",
                "task_id": "task-1",
                "created_by": "agent-1",
            },
            headers=make_auth_headers("ceo"),
        )
        resp = test_client.get("/api/v1/artifacts")
        assert resp.status_code == 200
        body = resp.json()
        assert body["pagination"]["total"] == 2

    def test_list_artifacts_filter_by_task_id(
        self, test_client: TestClient[Any]
    ) -> None:
        test_client.post(
            "/api/v1/artifacts",
            json={
                "type": "code",
                "path": "src/a.py",
                "task_id": "task-A",
                "created_by": "agent-1",
            },
            headers=make_auth_headers("ceo"),
        )
        test_client.post(
            "/api/v1/artifacts",
            json={
                "type": "code",
                "path": "src/b.py",
                "task_id": "task-B",
                "created_by": "agent-1",
            },
            headers=make_auth_headers("ceo"),
        )
        resp = test_client.get("/api/v1/artifacts?task_id=task-A")
        assert resp.status_code == 200
        body = resp.json()
        assert body["pagination"]["total"] == 1
        assert body["data"][0]["task_id"] == "task-A"

    def test_oversized_artifact_id_rejected(self, test_client: TestClient[Any]) -> None:
        long_id = "x" * 129
        resp = test_client.get(
            f"/api/v1/artifacts/{long_id}",
            headers=make_auth_headers("ceo"),
        )
        assert resp.status_code == 400
