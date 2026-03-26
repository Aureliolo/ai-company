"""Tests for department policies on built-in templates (#723)."""

import pytest

from synthorg.config.schema import RootConfig
from synthorg.core.company import ApprovalChain, Department
from synthorg.templates.loader import load_template
from synthorg.templates.renderer import render_template

# -- Helpers ───────────────────────────────────────────────────────


def _get_dept(config: RootConfig, name: str) -> Department:
    """Find a department by name in a rendered config."""
    for d in config.departments:
        if d.name == name:
            return d
    available = [d.name for d in config.departments]
    pytest.fail(f"Department {name!r} not found; available: {available}")


def _get_chain(dept: Department, action_type: str) -> ApprovalChain:
    """Find an approval chain by action type in a department."""
    for c in dept.policies.approval_chains:
        if c.action_type == action_type:
            return c
    existing = [c.action_type for c in dept.policies.approval_chains]
    pytest.fail(
        f"No approval chain {action_type!r} in department "
        f"{dept.name!r}; existing: {existing}"
    )


# -- Fixtures ──────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def dev_shop_config() -> RootConfig:
    """Render the dev_shop template once for all tests."""
    return render_template(load_template("dev_shop"))


@pytest.fixture(scope="module")
def product_team_config() -> RootConfig:
    """Render the product_team template once for all tests."""
    return render_template(load_template("product_team"))


@pytest.fixture(scope="module")
def agency_config() -> RootConfig:
    """Render the agency template once for all tests."""
    return render_template(load_template("agency"))


@pytest.fixture(scope="module")
def full_company_config() -> RootConfig:
    """Render the full_company template once for all tests."""
    return render_template(load_template("full_company"))


# -- Tests ─────────────────────────────────────────────────────────


@pytest.mark.unit
class TestBuiltinDepartmentPolicies:
    """Verify department policies on built-in templates (#723)."""

    # -- engineering review requirements (parametrized) ────────────

    @pytest.mark.parametrize(
        ("template_name", "expected_reviewers"),
        [
            ("dev_shop", 1),
            ("product_team", 1),
            ("agency", 1),
            ("full_company", 2),
        ],
    )
    def test_engineering_review_requirements(
        self,
        template_name: str,
        expected_reviewers: int,
    ) -> None:
        config = render_template(load_template(template_name))
        eng = _get_dept(config, "engineering")
        assert eng.policies.review_requirements.min_reviewers == expected_reviewers

    # -- dev_shop ──────────────────────────────────────────────────

    def test_dev_shop_qa_test_coverage_chain(
        self,
        dev_shop_config: RootConfig,
    ) -> None:
        qa = _get_dept(dev_shop_config, "quality_assurance")
        chain = _get_chain(qa, "test_coverage")
        assert "QA Lead" in chain.approvers

    def test_dev_shop_operations_default_policies(
        self,
        dev_shop_config: RootConfig,
    ) -> None:
        ops = _get_dept(dev_shop_config, "operations")
        assert ops.policies.approval_chains == ()

    # -- product_team ──────────────────────────────────────────────

    def test_product_team_design_review_chain(
        self,
        product_team_config: RootConfig,
    ) -> None:
        design = _get_dept(product_team_config, "design")
        chain = _get_chain(design, "design_review")
        assert "UX Designer" in chain.approvers

    # -- agency ────────────────────────────────────────────────────

    def test_agency_operations_client_approval_chain(
        self,
        agency_config: RootConfig,
    ) -> None:
        ops = _get_dept(agency_config, "operations")
        chain = _get_chain(ops, "client_approval")
        assert "Project Manager" in chain.approvers

    # -- full_company ──────────────────────────────────────────────

    def test_full_company_engineering_code_review_chain(
        self,
        full_company_config: RootConfig,
    ) -> None:
        eng = _get_dept(full_company_config, "engineering")
        chain = _get_chain(eng, "code_review")
        assert chain.approvers == ("Software Architect", "CTO")

    def test_full_company_security_review_chain(
        self,
        full_company_config: RootConfig,
    ) -> None:
        sec = _get_dept(full_company_config, "security")
        chain = _get_chain(sec, "security_review")
        assert chain.approvers == ("Security Engineer", "CTO")

    def test_full_company_operations_change_management_chain(
        self,
        full_company_config: RootConfig,
    ) -> None:
        ops = _get_dept(full_company_config, "operations")
        chain = _get_chain(ops, "change_management")
        assert "COO" in chain.approvers
