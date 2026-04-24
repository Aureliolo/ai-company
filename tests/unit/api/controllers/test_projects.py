"""Tests for project controller."""

from typing import Any

import pytest
from litestar.testing import TestClient

from tests.unit.api.conftest import make_auth_headers


@pytest.mark.unit
class TestProjectController:
    def test_list_projects_empty(self, test_client: TestClient[Any]) -> None:
        resp = test_client.get("/api/v1/projects")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"] == []
        assert body["pagination"]["total"] == 0

    def test_get_project_not_found(self, test_client: TestClient[Any]) -> None:
        resp = test_client.get("/api/v1/projects/nonexistent")
        assert resp.status_code == 404
        body = resp.json()
        assert body["success"] is False
        assert "not found" in body["error"].lower()

    def test_create_and_get_project(self, test_client: TestClient[Any]) -> None:
        create_resp = test_client.post(
            "/api/v1/projects",
            json={
                "name": "Auth System",
                "description": "Build authentication",
                "budget": 500.0,
            },
            headers=make_auth_headers("ceo"),
        )
        assert create_resp.status_code == 201
        created = create_resp.json()
        assert created["success"] is True
        project_id = created["data"]["id"]
        assert project_id.startswith("proj-")
        assert created["data"]["name"] == "Auth System"
        assert created["data"]["budget"] == 500.0

        get_resp = test_client.get(f"/api/v1/projects/{project_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["data"]["id"] == project_id

    def test_list_projects_after_create(self, test_client: TestClient[Any]) -> None:
        test_client.post(
            "/api/v1/projects",
            json={"name": "P1"},
            headers=make_auth_headers("ceo"),
        )
        test_client.post(
            "/api/v1/projects",
            json={"name": "P2"},
            headers=make_auth_headers("ceo"),
        )
        resp = test_client.get("/api/v1/projects")
        assert resp.status_code == 200
        body = resp.json()
        assert body["pagination"]["total"] == 2
        assert len(body["data"]) == 2

    def test_create_project_with_deadline(self, test_client: TestClient[Any]) -> None:
        resp = test_client.post(
            "/api/v1/projects",
            json={
                "name": "Deadline Project",
                "deadline": "2026-12-31",
            },
            headers=make_auth_headers("ceo"),
        )
        assert resp.status_code == 201
        assert resp.json()["data"]["deadline"] == "2026-12-31"

    def test_create_project_invalid_deadline(
        self, test_client: TestClient[Any]
    ) -> None:
        resp = test_client.post(
            "/api/v1/projects",
            json={
                "name": "Bad Deadline",
                "deadline": "not-a-date",
            },
            headers=make_auth_headers("ceo"),
        )
        assert resp.status_code == 400

    def test_oversized_project_id_rejected(self, test_client: TestClient[Any]) -> None:
        long_id = "x" * 129
        resp = test_client.get(f"/api/v1/projects/{long_id}")
        assert resp.status_code == 400

    def test_list_projects_filter_by_invalid_status(
        self, test_client: TestClient[Any]
    ) -> None:
        resp = test_client.get("/api/v1/projects?status=bogus")
        # ApiValidationError is 422 Unprocessable Entity (RFC 9457).
        assert resp.status_code == 422
        body = resp.json()
        assert body["success"] is False
        assert "Invalid project status" in body["error"]
        assert body["error_detail"]["error_category"] == "validation"

    def test_create_project_with_duplicate_team(
        self, test_client: TestClient[Any]
    ) -> None:
        resp = test_client.post(
            "/api/v1/projects",
            json={
                "name": "Dupe Team",
                "team": ["agent-1", "agent-1"],
            },
            headers=make_auth_headers("ceo"),
        )
        assert resp.status_code == 400

    def test_delete_project_succeeds(self, test_client: TestClient[Any]) -> None:
        create_resp = test_client.post(
            "/api/v1/projects",
            json={"name": "To be deleted"},
            headers=make_auth_headers("ceo"),
        )
        assert create_resp.status_code == 201
        project_id = create_resp.json()["data"]["id"]

        delete_resp = test_client.delete(
            f"/api/v1/projects/{project_id}",
            headers=make_auth_headers("ceo"),
        )
        assert delete_resp.status_code == 204

        # Subsequent fetch must 404.
        get_resp = test_client.get(f"/api/v1/projects/{project_id}")
        assert get_resp.status_code == 404

    def test_delete_project_not_found(self, test_client: TestClient[Any]) -> None:
        resp = test_client.delete(
            "/api/v1/projects/proj-does-not-exist",
            headers=make_auth_headers("ceo"),
        )
        assert resp.status_code == 404
        body = resp.json()
        assert body["success"] is False
        assert "not found" in body["error"].lower()
