"""Tests for config version history API endpoints.

Covers BudgetConfigVersionController, CompanyVersionController,
and EvaluationConfigVersionController.
"""

from datetime import UTC, datetime
from typing import Any

import pytest
from litestar.testing import TestClient

from synthorg.budget.config import BudgetConfig
from synthorg.core.company import Company
from synthorg.hr.evaluation.config import EvaluationConfig
from synthorg.versioning import VersionSnapshot, compute_content_hash
from tests.unit.api.conftest import make_auth_headers

_NOW = datetime(2026, 4, 8, 12, 0, tzinfo=UTC)


def _snap[T](
    entity_id: str,
    model: T,
    version: int = 1,
) -> VersionSnapshot[T]:
    return VersionSnapshot(
        entity_id=entity_id,
        version=version,
        content_hash=compute_content_hash(model),
        snapshot=model,
        saved_by="test-user",
        saved_at=_NOW,
    )


# ── BudgetConfigVersionController ──────────────────────────────


class TestBudgetConfigVersions:
    """GET /budget/config/versions endpoints."""

    @pytest.mark.unit
    def test_list_versions_empty(
        self,
        test_client: TestClient[Any],
    ) -> None:
        resp = test_client.get(
            "/api/v1/budget/config/versions",
            headers=make_auth_headers("ceo"),
        )
        assert resp.status_code == 200
        assert resp.json()["data"] == []
        assert resp.json()["pagination"]["total"] == 0

    @pytest.mark.unit
    async def test_list_versions_with_data(
        self,
        test_client: TestClient[Any],
        fake_persistence: Any,
    ) -> None:
        repo = fake_persistence.budget_config_versions
        c1 = BudgetConfig(total_monthly=100.0)
        c2 = BudgetConfig(total_monthly=200.0)
        await repo.save_version(_snap("default", c1, version=1))
        await repo.save_version(_snap("default", c2, version=2))

        resp = test_client.get(
            "/api/v1/budget/config/versions",
            headers=make_auth_headers("ceo"),
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == 2
        assert data[0]["version"] == 2
        assert data[1]["version"] == 1

    @pytest.mark.unit
    async def test_get_version(
        self,
        test_client: TestClient[Any],
        fake_persistence: Any,
    ) -> None:
        repo = fake_persistence.budget_config_versions
        config = BudgetConfig(total_monthly=150.0)
        await repo.save_version(_snap("default", config))

        resp = test_client.get(
            "/api/v1/budget/config/versions/1",
            headers=make_auth_headers("ceo"),
        )
        assert resp.status_code == 200
        snap = resp.json()["data"]
        assert snap["version"] == 1
        assert snap["snapshot"]["total_monthly"] == 150.0

    @pytest.mark.unit
    def test_get_version_not_found(
        self,
        test_client: TestClient[Any],
    ) -> None:
        resp = test_client.get(
            "/api/v1/budget/config/versions/99",
            headers=make_auth_headers("ceo"),
        )
        assert resp.status_code == 404

    @pytest.mark.unit
    async def test_list_versions_paginated(
        self,
        test_client: TestClient[Any],
        fake_persistence: Any,
    ) -> None:
        repo = fake_persistence.budget_config_versions
        for v in range(1, 4):
            c = BudgetConfig(total_monthly=float(v * 100))
            await repo.save_version(_snap("default", c, version=v))

        resp = test_client.get(
            "/api/v1/budget/config/versions?limit=2&offset=0",
            headers=make_auth_headers("ceo"),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) == 2
        assert body["pagination"]["total"] == 3


# ── CompanyVersionController ───────────────────────────────────


class TestCompanyVersions:
    """GET /company/versions endpoints."""

    @pytest.mark.unit
    def test_list_versions_empty(
        self,
        test_client: TestClient[Any],
    ) -> None:
        resp = test_client.get(
            "/api/v1/company/versions",
            headers=make_auth_headers("ceo"),
        )
        assert resp.status_code == 200
        assert resp.json()["data"] == []

    @pytest.mark.unit
    async def test_get_version(
        self,
        test_client: TestClient[Any],
        fake_persistence: Any,
    ) -> None:
        repo = fake_persistence.company_versions
        company = Company(name="Test Corp")
        await repo.save_version(_snap("default", company))

        resp = test_client.get(
            "/api/v1/company/versions/1",
            headers=make_auth_headers("ceo"),
        )
        assert resp.status_code == 200
        snap = resp.json()["data"]
        assert snap["version"] == 1
        assert snap["snapshot"]["name"] == "Test Corp"

    @pytest.mark.unit
    def test_get_version_not_found(
        self,
        test_client: TestClient[Any],
    ) -> None:
        resp = test_client.get(
            "/api/v1/company/versions/99",
            headers=make_auth_headers("ceo"),
        )
        assert resp.status_code == 404


# ── EvaluationConfigVersionController ──────────────────────────


class TestEvaluationConfigVersions:
    """GET /evaluation/config/versions endpoints."""

    @pytest.mark.unit
    def test_list_versions_empty(
        self,
        test_client: TestClient[Any],
    ) -> None:
        resp = test_client.get(
            "/api/v1/evaluation/config/versions",
            headers=make_auth_headers("ceo"),
        )
        assert resp.status_code == 200
        assert resp.json()["data"] == []

    @pytest.mark.unit
    async def test_get_version(
        self,
        test_client: TestClient[Any],
        fake_persistence: Any,
    ) -> None:
        repo = fake_persistence.evaluation_config_versions
        config = EvaluationConfig()
        await repo.save_version(_snap("default", config))

        resp = test_client.get(
            "/api/v1/evaluation/config/versions/1",
            headers=make_auth_headers("ceo"),
        )
        assert resp.status_code == 200
        snap = resp.json()["data"]
        assert snap["version"] == 1

    @pytest.mark.unit
    def test_get_version_not_found(
        self,
        test_client: TestClient[Any],
    ) -> None:
        resp = test_client.get(
            "/api/v1/evaluation/config/versions/99",
            headers=make_auth_headers("ceo"),
        )
        assert resp.status_code == 404
