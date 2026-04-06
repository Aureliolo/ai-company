"""Tests for company mutation endpoints."""

from typing import Any

import pytest
from litestar.testing import TestClient

from tests.unit.api.conftest import make_auth_headers


@pytest.mark.unit
class TestUpdateCompany:
    def test_patch_company_happy_path(
        self,
        test_client: TestClient[Any],
    ) -> None:
        resp = test_client.patch(
            "/api/v1/company",
            json={"company_name": "New Name"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["company_name"] == "New Name"

    def test_patch_company_observer_denied(
        self,
        test_client: TestClient[Any],
    ) -> None:
        resp = test_client.patch(
            "/api/v1/company",
            json={"company_name": "New Name"},
            headers=make_auth_headers("observer"),
        )
        assert resp.status_code == 403


@pytest.mark.unit
class TestReorderDepartments:
    def test_reorder_two_departments(
        self,
        test_client: TestClient[Any],
    ) -> None:
        # Create two departments and reorder them
        test_client.post(
            "/api/v1/departments",
            json={"name": "alpha"},
        )
        test_client.post(
            "/api/v1/departments",
            json={"name": "beta"},
        )
        resp = test_client.post(
            "/api/v1/company/reorder-departments",
            json={"department_names": ["beta", "alpha"]},
        )
        assert resp.status_code == 200
        names = [d["name"] for d in resp.json()["data"]]
        assert names == ["beta", "alpha"]

    def test_reorder_observer_denied(
        self,
        test_client: TestClient[Any],
    ) -> None:
        resp = test_client.post(
            "/api/v1/company/reorder-departments",
            json={"department_names": []},
            headers=make_auth_headers("observer"),
        )
        assert resp.status_code == 403
