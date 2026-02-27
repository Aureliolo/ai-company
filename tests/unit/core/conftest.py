"""Unit test configuration and fixtures for core models."""

from datetime import date
from uuid import uuid4

import pytest
from polyfactory.factories.pydantic_factory import ModelFactory

from ai_company.core.agent import (
    AgentIdentity,
    MemoryConfig,
    ModelConfig,
    PersonalityConfig,
    SkillSet,
    ToolPermissions,
)
from ai_company.core.company import (
    Company,
    CompanyConfig,
    Department,
    HRRegistry,
    Team,
)
from ai_company.core.enums import (
    DepartmentName,
    ProficiencyLevel,
    SeniorityLevel,
    SkillCategory,
)
from ai_company.core.role import Authority, CustomRole, Role, SeniorityInfo, Skill

# ── Factories ──────────────────────────────────────────────────────


class SkillFactory(ModelFactory):
    __model__ = Skill


class AuthorityFactory(ModelFactory):
    __model__ = Authority


class SeniorityInfoFactory(ModelFactory):
    __model__ = SeniorityInfo


class RoleFactory(ModelFactory):
    __model__ = Role


class CustomRoleFactory(ModelFactory):
    __model__ = CustomRole


class PersonalityConfigFactory(ModelFactory):
    __model__ = PersonalityConfig


class SkillSetFactory(ModelFactory):
    __model__ = SkillSet


class ModelConfigFactory(ModelFactory):
    __model__ = ModelConfig
    temperature = 0.7


class MemoryConfigFactory(ModelFactory):
    __model__ = MemoryConfig


class ToolPermissionsFactory(ModelFactory):
    __model__ = ToolPermissions


class AgentIdentityFactory(ModelFactory):
    __model__ = AgentIdentity


class TeamFactory(ModelFactory):
    __model__ = Team


class DepartmentFactory(ModelFactory):
    __model__ = Department
    budget_percent = 10.0


class CompanyConfigFactory(ModelFactory):
    __model__ = CompanyConfig


class HRRegistryFactory(ModelFactory):
    __model__ = HRRegistry


class CompanyFactory(ModelFactory):
    __model__ = Company
    departments = ()


# ── Sample Fixtures ────────────────────────────────────────────────


@pytest.fixture
def sample_skill() -> Skill:
    return Skill(
        name="python",
        category=SkillCategory.ENGINEERING,
        proficiency=ProficiencyLevel.ADVANCED,
    )


@pytest.fixture
def sample_authority() -> Authority:
    return Authority(
        can_approve=("code_reviews",),
        reports_to="engineering_lead",
        can_delegate_to=("junior_developers",),
        budget_limit=5.0,
    )


@pytest.fixture
def sample_role() -> Role:
    return Role(
        name="Backend Developer",
        department=DepartmentName.ENGINEERING,
        required_skills=("python", "apis", "databases"),
        authority_level=SeniorityLevel.MID,
        description="APIs, business logic, databases",
    )


@pytest.fixture
def sample_model_config() -> ModelConfig:
    return ModelConfig(
        provider="anthropic",
        model_id="claude-sonnet-4-6",
        temperature=0.3,
        max_tokens=8192,
        fallback_model="openrouter/anthropic/claude-haiku",
    )


@pytest.fixture
def sample_agent(sample_model_config: ModelConfig) -> AgentIdentity:
    return AgentIdentity(
        id=uuid4(),
        name="Sarah Chen",
        role="Senior Backend Developer",
        department="Engineering",
        level=SeniorityLevel.SENIOR,
        model=sample_model_config,
        hiring_date=date(2026, 2, 27),
    )


@pytest.fixture
def sample_department() -> Department:
    return Department(
        name="Engineering",
        head="cto",
        budget_percent=60.0,
        teams=(
            Team(
                name="backend",
                lead="backend_lead",
                members=("sr_backend_1", "mid_backend_1"),
            ),
        ),
    )


@pytest.fixture
def sample_company(sample_department: Department) -> Company:
    return Company(
        name="Test Corp",
        departments=(sample_department,),
        config=CompanyConfig(budget_monthly=100.0),
    )
