"""Tests for company structure and configuration models."""

import pytest
from pydantic import ValidationError

from ai_company.core.company import (
    Company,
    CompanyConfig,
    Department,
    HRRegistry,
    Team,
)
from ai_company.core.enums import CompanyType

from .conftest import (
    CompanyConfigFactory,
    CompanyFactory,
    DepartmentFactory,
    HRRegistryFactory,
    TeamFactory,
)

# ── Team ───────────────────────────────────────────────────────────


@pytest.mark.unit
class TestTeam:
    def test_valid_team(self) -> None:
        team = Team(
            name="backend",
            lead="backend_lead",
            members=("dev_1", "dev_2"),
        )
        assert team.name == "backend"
        assert team.lead == "backend_lead"
        assert len(team.members) == 2

    def test_defaults(self) -> None:
        team = Team(name="test", lead="lead")
        assert team.members == ()

    def test_empty_name_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Team(name="", lead="lead")

    def test_empty_lead_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Team(name="test", lead="")

    def test_frozen(self) -> None:
        team = Team(name="test", lead="lead")
        with pytest.raises(ValidationError):
            team.name = "changed"  # type: ignore[misc]

    def test_factory(self) -> None:
        team = TeamFactory.build()
        assert isinstance(team, Team)


# ── Department ─────────────────────────────────────────────────────


@pytest.mark.unit
class TestDepartment:
    def test_valid_department(self, sample_department: Department) -> None:
        assert sample_department.name == "Engineering"
        assert sample_department.head == "cto"
        assert sample_department.budget_percent == 60.0
        assert len(sample_department.teams) == 1

    def test_defaults(self) -> None:
        dept = Department(name="Test", head="head")
        assert dept.budget_percent == 0.0
        assert dept.teams == ()

    def test_budget_percent_zero(self) -> None:
        dept = Department(name="Test", head="head", budget_percent=0.0)
        assert dept.budget_percent == 0.0

    def test_budget_percent_hundred(self) -> None:
        dept = Department(name="Test", head="head", budget_percent=100.0)
        assert dept.budget_percent == 100.0

    def test_budget_percent_negative_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Department(name="Test", head="head", budget_percent=-1.0)

    def test_budget_percent_over_hundred_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Department(name="Test", head="head", budget_percent=100.1)

    def test_duplicate_team_names_rejected(self) -> None:
        with pytest.raises(ValidationError, match="Duplicate team names"):
            Department(
                name="Eng",
                head="head",
                teams=(
                    Team(name="backend", lead="a"),
                    Team(name="backend", lead="b"),
                ),
            )

    def test_frozen(self, sample_department: Department) -> None:
        with pytest.raises(ValidationError):
            sample_department.name = "Changed"  # type: ignore[misc]

    def test_factory(self) -> None:
        dept = DepartmentFactory.build()
        assert isinstance(dept, Department)
        assert 0.0 <= dept.budget_percent <= 100.0


# ── CompanyConfig ──────────────────────────────────────────────────


@pytest.mark.unit
class TestCompanyConfig:
    def test_defaults(self) -> None:
        cfg = CompanyConfig()
        assert cfg.autonomy == 0.5
        assert cfg.budget_monthly == 100.0
        assert cfg.communication_pattern == "hybrid"
        assert cfg.tool_access_default == ()

    def test_autonomy_boundaries(self) -> None:
        low = CompanyConfig(autonomy=0.0)
        high = CompanyConfig(autonomy=1.0)
        assert low.autonomy == 0.0
        assert high.autonomy == 1.0

    def test_autonomy_below_zero_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CompanyConfig(autonomy=-0.1)

    def test_autonomy_above_one_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CompanyConfig(autonomy=1.1)

    def test_budget_negative_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CompanyConfig(budget_monthly=-1.0)

    def test_empty_communication_pattern_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CompanyConfig(communication_pattern="")

    def test_frozen(self) -> None:
        cfg = CompanyConfig()
        with pytest.raises(ValidationError):
            cfg.autonomy = 1.0  # type: ignore[misc]

    def test_factory(self) -> None:
        cfg = CompanyConfigFactory.build()
        assert isinstance(cfg, CompanyConfig)


# ── HRRegistry ─────────────────────────────────────────────────────


@pytest.mark.unit
class TestHRRegistry:
    def test_defaults(self) -> None:
        hr = HRRegistry()
        assert hr.active_agents == ()
        assert hr.available_roles == ()
        assert hr.hiring_queue == ()

    def test_custom_values(self) -> None:
        hr = HRRegistry(
            active_agents=("agent_1",),
            available_roles=("dev", "pm"),
            hiring_queue=("designer",),
        )
        assert len(hr.active_agents) == 1
        assert len(hr.available_roles) == 2

    def test_duplicate_active_agents_rejected(self) -> None:
        with pytest.raises(ValidationError, match="Duplicate entries"):
            HRRegistry(active_agents=("alice", "alice"))

    def test_frozen(self) -> None:
        hr = HRRegistry()
        with pytest.raises(ValidationError):
            hr.active_agents = ("new",)  # type: ignore[misc]

    def test_factory(self) -> None:
        hr = HRRegistryFactory.build()
        assert isinstance(hr, HRRegistry)


# ── Company ────────────────────────────────────────────────────────


@pytest.mark.unit
class TestCompany:
    def test_valid_company(self, sample_company: Company) -> None:
        assert sample_company.name == "Test Corp"
        assert len(sample_company.departments) == 1
        assert sample_company.config.budget_monthly == 100.0

    def test_defaults(self) -> None:
        co = Company(name="Minimal")
        assert co.type is CompanyType.CUSTOM
        assert co.departments == ()
        assert isinstance(co.config, CompanyConfig)
        assert isinstance(co.hr_registry, HRRegistry)

    def test_budget_sum_at_100_accepted(self) -> None:
        depts = (
            Department(name="A", head="a", budget_percent=60.0),
            Department(name="B", head="b", budget_percent=40.0),
        )
        co = Company(name="Full Budget", departments=depts)
        assert sum(d.budget_percent for d in co.departments) == 100.0

    def test_budget_sum_under_100_accepted(self) -> None:
        depts = (
            Department(name="A", head="a", budget_percent=50.0),
            Department(name="B", head="b", budget_percent=30.0),
        )
        co = Company(name="With Reserve", departments=depts)
        assert sum(d.budget_percent for d in co.departments) == 80.0

    def test_budget_sum_over_100_rejected(self) -> None:
        depts = (
            Department(name="A", head="a", budget_percent=60.0),
            Department(name="B", head="b", budget_percent=50.0),
        )
        with pytest.raises(ValidationError, match="exceeding 100%"):
            Company(name="Over Budget", departments=depts)

    def test_budget_sum_barely_over_100_rejected(self) -> None:
        depts = (
            Department(name="A", head="a", budget_percent=50.01),
            Department(name="B", head="b", budget_percent=50.0),
        )
        with pytest.raises(ValidationError, match="exceeding 100%"):
            Company(name="Just Over", departments=depts)

    def test_duplicate_department_names_rejected(self) -> None:
        depts = (
            Department(name="Engineering", head="a", budget_percent=30.0),
            Department(name="Engineering", head="b", budget_percent=20.0),
        )
        with pytest.raises(ValidationError, match="Duplicate department names"):
            Company(name="Dup Depts", departments=depts)

    def test_empty_departments_accepted(self) -> None:
        co = Company(name="Empty")
        assert co.departments == ()

    def test_frozen(self, sample_company: Company) -> None:
        with pytest.raises(ValidationError):
            sample_company.name = "Changed"  # type: ignore[misc]

    def test_model_copy_update(self, sample_company: Company) -> None:
        updated = sample_company.model_copy(update={"name": "New Corp"})
        assert updated.name == "New Corp"
        assert sample_company.name == "Test Corp"

    def test_json_roundtrip(self, sample_company: Company) -> None:
        json_str = sample_company.model_dump_json()
        restored = Company.model_validate_json(json_str)
        assert restored.name == sample_company.name
        assert len(restored.departments) == len(sample_company.departments)

    def test_factory(self) -> None:
        co = CompanyFactory.build()
        assert isinstance(co, Company)
