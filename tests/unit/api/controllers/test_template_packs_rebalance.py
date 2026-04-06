"""Tests for budget rebalancing on template pack application."""

import json
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import patch

import pytest
from litestar.testing import TestClient

from synthorg.templates.schema import TemplateDepartmentConfig
from tests.unit.api.conftest import make_auth_headers


def _seed_departments(
    test_client: TestClient[Any],
    depts: list[dict[str, Any]],
) -> None:
    """Seed departments into settings."""
    resp = test_client.put(
        "/api/v1/settings/company/departments",
        json={"value": json.dumps(depts)},
        headers=make_auth_headers("ceo"),
    )
    assert resp.status_code == 200, f"Failed to seed departments: {resp.text}"


def _dept(name: str, budget: float) -> dict[str, Any]:
    return {"name": name, "budget_percent": budget}


_FAKE_PACK_DEPT_BUDGET = 8.0
_FAKE_PACK_NAME = "test-pack"


@dataclass(frozen=True)
class _FakeTemplate:
    """Minimal stand-in for CompanyTemplate with departments + agents."""

    departments: tuple[TemplateDepartmentConfig, ...] = ()
    agents: tuple[Any, ...] = ()


@dataclass(frozen=True)
class _FakeLoadedTemplate:
    """Minimal stand-in for LoadedTemplate."""

    template: _FakeTemplate = field(default_factory=_FakeTemplate)
    raw_yaml: str = ""
    source_name: str = "test"


def _make_fake_loaded(
    dept_budget: float = _FAKE_PACK_DEPT_BUDGET,
) -> _FakeLoadedTemplate:
    """Create a fake LoadedTemplate with one department."""
    dept = TemplateDepartmentConfig(
        name="test-dept",
        budget_percent=dept_budget,
    )
    return _FakeLoadedTemplate(
        template=_FakeTemplate(departments=(dept,)),
    )


@pytest.mark.unit
class TestPackApplyRebalance:
    """Tests for rebalance_mode on POST /template-packs/apply."""

    def _apply(
        self,
        test_client: TestClient[Any],
        pack_name: str = _FAKE_PACK_NAME,
        rebalance_mode: str | None = None,
        dept_budget: float = _FAKE_PACK_DEPT_BUDGET,
    ) -> Any:
        """Apply a template pack with optional rebalance_mode."""
        body: dict[str, Any] = {"pack_name": pack_name}
        if rebalance_mode is not None:
            body["rebalance_mode"] = rebalance_mode
        fake = _make_fake_loaded(dept_budget)
        with (
            patch(
                "synthorg.api.controllers.template_packs.load_pack",
                return_value=fake,
            ),
            patch(
                "synthorg.api.controllers.template_packs.expand_template_agents",
                return_value=[],
            ),
        ):
            return test_client.post(
                "/api/v1/template-packs/apply",
                json=body,
            )

    def test_default_mode_is_scale_existing(
        self,
        test_client: TestClient[Any],
    ) -> None:
        _seed_departments(
            test_client,
            [_dept("eng", 60), _dept("prod", 40)],
        )
        resp = self._apply(test_client)
        assert resp.status_code == 201
        body = resp.json()["data"]
        assert body["rebalance_mode"] == "scale_existing"
        assert body["scale_factor"] is not None

    def test_scale_existing_reduces_budgets(
        self,
        test_client: TestClient[Any],
    ) -> None:
        _seed_departments(
            test_client,
            [_dept("eng", 60), _dept("prod", 40)],
        )
        resp = self._apply(test_client, rebalance_mode="scale_existing")
        assert resp.status_code == 201
        body = resp.json()["data"]
        assert body["budget_before"] == pytest.approx(100.0, abs=0.1)
        assert body["budget_after"] == pytest.approx(100.0, abs=0.1)
        assert body["scale_factor"] == pytest.approx(0.92, abs=0.01)

    def test_scale_existing_no_scaling_when_under_budget(
        self,
        test_client: TestClient[Any],
    ) -> None:
        _seed_departments(
            test_client,
            [_dept("eng", 50), _dept("prod", 30)],
        )
        resp = self._apply(test_client, rebalance_mode="scale_existing")
        assert resp.status_code == 201
        body = resp.json()["data"]
        assert body["scale_factor"] == 1.0
        assert body["budget_after"] == pytest.approx(88.0, abs=0.1)

    def test_reject_if_over_returns_409(
        self,
        test_client: TestClient[Any],
    ) -> None:
        _seed_departments(
            test_client,
            [_dept("eng", 60), _dept("prod", 40)],
        )
        resp = self._apply(test_client, rebalance_mode="reject_if_over")
        assert resp.status_code == 409

    def test_reject_if_over_under_100_succeeds(
        self,
        test_client: TestClient[Any],
    ) -> None:
        _seed_departments(
            test_client,
            [_dept("eng", 50), _dept("prod", 30)],
        )
        resp = self._apply(test_client, rebalance_mode="reject_if_over")
        assert resp.status_code == 201

    def test_none_mode_no_adjustment(
        self,
        test_client: TestClient[Any],
    ) -> None:
        _seed_departments(
            test_client,
            [_dept("eng", 60), _dept("prod", 40)],
        )
        resp = self._apply(test_client, rebalance_mode="none")
        assert resp.status_code == 201
        body = resp.json()["data"]
        assert body["scale_factor"] is None
        assert body["budget_after"] == pytest.approx(108.0, abs=0.1)

    def test_response_includes_budget_fields(
        self,
        test_client: TestClient[Any],
    ) -> None:
        _seed_departments(test_client, [_dept("eng", 60)])
        resp = self._apply(test_client)
        assert resp.status_code == 201
        body = resp.json()["data"]
        assert "budget_before" in body
        assert "budget_after" in body
        assert "rebalance_mode" in body
        assert "scale_factor" in body

    def test_backward_compatible_without_rebalance_mode(
        self,
        test_client: TestClient[Any],
    ) -> None:
        """Omitting rebalance_mode defaults to scale_existing."""
        _seed_departments(
            test_client,
            [_dept("eng", 60), _dept("prod", 40)],
        )
        resp = self._apply(test_client)
        assert resp.status_code == 201
        assert resp.json()["data"]["rebalance_mode"] == "scale_existing"

    def test_no_existing_departments(
        self,
        test_client: TestClient[Any],
    ) -> None:
        resp = self._apply(test_client)
        assert resp.status_code == 201
        body = resp.json()["data"]
        assert body["budget_before"] == 0
        assert body["budget_after"] == pytest.approx(
            _FAKE_PACK_DEPT_BUDGET,
            abs=0.1,
        )
