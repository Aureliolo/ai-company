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
from ai_company.core.artifact import Artifact, ExpectedArtifact
from ai_company.core.company import (
    Company,
    CompanyConfig,
    Department,
    HRRegistry,
    Team,
)
from ai_company.core.enums import (
    ArtifactType,
    Complexity,
    DepartmentName,
    MemoryType,
    Priority,
    ProficiencyLevel,
    SeniorityLevel,
    SkillCategory,
    TaskStatus,
    TaskType,
)
from ai_company.core.project import Project
from ai_company.core.role import Authority, CustomRole, Role, SeniorityInfo, Skill
from ai_company.core.task import AcceptanceCriterion, Task

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
    type = MemoryType.SESSION


class ToolPermissionsFactory(ModelFactory):
    __model__ = ToolPermissions
    allowed = ()
    denied = ()


class AgentIdentityFactory(ModelFactory):
    __model__ = AgentIdentity
    memory = MemoryConfigFactory
    tools = ToolPermissionsFactory


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


class ExpectedArtifactFactory(ModelFactory):
    __model__ = ExpectedArtifact


class ArtifactFactory(ModelFactory):
    __model__ = Artifact


class AcceptanceCriterionFactory(ModelFactory):
    __model__ = AcceptanceCriterion


class TaskFactory(ModelFactory):
    __model__ = Task
    status = TaskStatus.CREATED
    assigned_to = None
    deadline = None


class ProjectFactory(ModelFactory):
    __model__ = Project
    deadline = None


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
        provider="test-provider",
        model_id="test-model-sonnet-4-6",
        temperature=0.3,
        max_tokens=8192,
        fallback_model="test-provider/test-model-haiku",
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


@pytest.fixture
def sample_expected_artifact() -> ExpectedArtifact:
    return ExpectedArtifact(type=ArtifactType.CODE, path="src/auth/")


@pytest.fixture
def sample_acceptance_criterion() -> AcceptanceCriterion:
    return AcceptanceCriterion(description="Unit tests pass with >80% coverage")


@pytest.fixture
def sample_task() -> Task:
    return Task(
        id="task-123",
        title="Implement user authentication",
        description="Create REST endpoints for login, register, logout",
        type=TaskType.DEVELOPMENT,
        priority=Priority.HIGH,
        project="proj-456",
        created_by="product_manager_1",
        estimated_complexity=Complexity.MEDIUM,
        budget_limit=2.0,
    )


@pytest.fixture
def sample_assigned_task() -> Task:
    """A task in ASSIGNED status."""
    return Task(
        id="task-123",
        title="Implement user authentication",
        description="Create REST endpoints for login, register, logout",
        type=TaskType.DEVELOPMENT,
        priority=Priority.HIGH,
        project="proj-456",
        created_by="product_manager_1",
        assigned_to="sarah_chen",
        status=TaskStatus.ASSIGNED,
    )


@pytest.fixture
def sample_project() -> Project:
    return Project(
        id="proj-456",
        name="Auth System",
        description="Implement full authentication system",
        team=("sarah_chen", "engineering_lead"),
        lead="engineering_lead",
        budget=10.0,
    )
