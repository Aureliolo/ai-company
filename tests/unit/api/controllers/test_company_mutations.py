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
        test_client.headers.update(make_auth_headers("observer"))
        resp = test_client.patch(
            "/api/v1/company",
            json={"company_name": "New Name"},
        )
        assert resp.status_code == 403


@pytest.mark.unit
class TestReorderDepartments:
    def test_reorder_empty_list(
        self,
        test_client: TestClient[Any],
    ) -> None:
        # No departments exist; reordering empty is valid
        # First create two departments
        test_client.post(
            "/api/v1/departments",
            json={"name": "alpha", "display_name": "Alpha"},
        )
        test_client.post(
            "/api/v1/departments",
            json={"name": "beta", "display_name": "Beta"},
        )
        resp = test_client.post(
            "/api/v1/company/reorder-departments",
            json={"department_names": ["beta", "alpha"]},
        )
        assert resp.status_code == 201
        names = [d["name"] for d in resp.json()["data"]]
        assert names == ["beta", "alpha"]

    def test_reorder_observer_denied(
        self,
        test_client: TestClient[Any],
    ) -> None:
        test_client.headers.update(make_auth_headers("observer"))
        resp = test_client.post(
            "/api/v1/company/reorder-departments",
            json={"department_names": []},
        )
        assert resp.status_code == 403
