"""Tests for core domain enumerations."""

import pytest

from ai_company.core.enums import (
    AgentStatus,
    ArtifactType,
    CompanyType,
    Complexity,
    CostTier,
    CreativityLevel,
    DepartmentName,
    MemoryType,
    Priority,
    ProficiencyLevel,
    ProjectStatus,
    RiskTolerance,
    SeniorityLevel,
    SkillCategory,
    TaskStatus,
    TaskType,
)

pytestmark = pytest.mark.timeout(30)

# ── Member Counts ──────────────────────────────────────────────────


@pytest.mark.unit
class TestEnumMemberCounts:
    def test_seniority_level_has_8_members(self) -> None:
        assert len(SeniorityLevel) == 8

    def test_agent_status_has_3_members(self) -> None:
        assert len(AgentStatus) == 3

    def test_risk_tolerance_has_3_members(self) -> None:
        assert len(RiskTolerance) == 3

    def test_creativity_level_has_3_members(self) -> None:
        assert len(CreativityLevel) == 3

    def test_memory_type_has_4_members(self) -> None:
        assert len(MemoryType) == 4

    def test_cost_tier_has_4_members(self) -> None:
        assert len(CostTier) == 4

    def test_company_type_has_8_members(self) -> None:
        assert len(CompanyType) == 8

    def test_skill_category_has_9_members(self) -> None:
        assert len(SkillCategory) == 9

    def test_proficiency_level_has_4_members(self) -> None:
        assert len(ProficiencyLevel) == 4

    def test_department_name_has_9_members(self) -> None:
        assert len(DepartmentName) == 9

    def test_task_status_has_7_members(self) -> None:
        assert len(TaskStatus) == 7

    def test_task_type_has_6_members(self) -> None:
        assert len(TaskType) == 6

    def test_priority_has_4_members(self) -> None:
        assert len(Priority) == 4

    def test_complexity_has_4_members(self) -> None:
        assert len(Complexity) == 4

    def test_artifact_type_has_3_members(self) -> None:
        assert len(ArtifactType) == 3

    def test_project_status_has_5_members(self) -> None:
        assert len(ProjectStatus) == 5


# ── String Values ──────────────────────────────────────────────────


@pytest.mark.unit
class TestEnumStringValues:
    def test_seniority_levels_are_lowercase(self) -> None:
        for member in SeniorityLevel:
            assert member.value == member.value.lower()

    def test_agent_status_values(self) -> None:
        assert AgentStatus.ACTIVE == "active"
        assert AgentStatus.ON_LEAVE == "on_leave"
        assert AgentStatus.TERMINATED == "terminated"

    def test_cost_tier_values(self) -> None:
        assert CostTier.LOW == "low"
        assert CostTier.MEDIUM == "medium"
        assert CostTier.HIGH == "high"
        assert CostTier.PREMIUM == "premium"

    def test_company_type_values(self) -> None:
        assert CompanyType.SOLO_FOUNDER == "solo_founder"
        assert CompanyType.STARTUP == "startup"
        assert CompanyType.CUSTOM == "custom"

    def test_task_status_values(self) -> None:
        assert TaskStatus.CREATED == "created"
        assert TaskStatus.ASSIGNED == "assigned"
        assert TaskStatus.IN_PROGRESS == "in_progress"
        assert TaskStatus.IN_REVIEW == "in_review"
        assert TaskStatus.COMPLETED == "completed"
        assert TaskStatus.BLOCKED == "blocked"
        assert TaskStatus.CANCELLED == "cancelled"

    def test_task_type_values(self) -> None:
        assert TaskType.DEVELOPMENT == "development"
        assert TaskType.DESIGN == "design"
        assert TaskType.RESEARCH == "research"
        assert TaskType.REVIEW == "review"
        assert TaskType.MEETING == "meeting"
        assert TaskType.ADMIN == "admin"

    def test_priority_values(self) -> None:
        assert Priority.CRITICAL == "critical"
        assert Priority.HIGH == "high"
        assert Priority.MEDIUM == "medium"
        assert Priority.LOW == "low"

    def test_complexity_values(self) -> None:
        assert Complexity.SIMPLE == "simple"
        assert Complexity.MEDIUM == "medium"
        assert Complexity.COMPLEX == "complex"
        assert Complexity.EPIC == "epic"

    def test_artifact_type_values(self) -> None:
        assert ArtifactType.CODE == "code"
        assert ArtifactType.TESTS == "tests"
        assert ArtifactType.DOCUMENTATION == "documentation"

    def test_project_status_values(self) -> None:
        assert ProjectStatus.PLANNING == "planning"
        assert ProjectStatus.ACTIVE == "active"
        assert ProjectStatus.ON_HOLD == "on_hold"
        assert ProjectStatus.COMPLETED == "completed"
        assert ProjectStatus.CANCELLED == "cancelled"


# ── StrEnum Behavior ───────────────────────────────────────────────


@pytest.mark.unit
class TestStrEnumBehavior:
    def test_strenum_is_string(self) -> None:
        assert isinstance(SeniorityLevel.JUNIOR, str)

    def test_strenum_equality_with_string(self) -> None:
        assert SeniorityLevel.JUNIOR == "junior"

    def test_strenum_iteration(self) -> None:
        levels = list(SeniorityLevel)
        assert len(levels) == 8
        assert levels[0] == SeniorityLevel.JUNIOR

    def test_strenum_membership(self) -> None:
        assert "senior" in [m.value for m in SeniorityLevel]

    def test_strenum_from_value(self) -> None:
        assert SeniorityLevel("junior") is SeniorityLevel.JUNIOR

    def test_strenum_invalid_value_raises(self) -> None:
        with pytest.raises(ValueError, match="not_a_level"):
            SeniorityLevel("not_a_level")


# ── Pydantic Integration ──────────────────────────────────────────


@pytest.mark.unit
class TestEnumPydanticIntegration:
    def test_enum_serializes_as_string(self) -> None:
        from pydantic import BaseModel

        class _M(BaseModel):
            level: SeniorityLevel

        m = _M(level=SeniorityLevel.SENIOR)
        dumped = m.model_dump()
        assert dumped["level"] == "senior"

    def test_enum_deserializes_from_string(self) -> None:
        from pydantic import BaseModel

        class _M(BaseModel):
            level: SeniorityLevel

        m = _M.model_validate({"level": "senior"})
        assert m.level is SeniorityLevel.SENIOR

    def test_enum_invalid_value_rejected(self) -> None:
        from pydantic import BaseModel, ValidationError

        class _M(BaseModel):
            level: SeniorityLevel

        with pytest.raises(ValidationError):
            _M.model_validate({"level": "invalid"})

    def test_enum_json_roundtrip(self) -> None:
        from pydantic import BaseModel

        class _M(BaseModel):
            status: AgentStatus
            tier: CostTier

        m = _M(status=AgentStatus.ACTIVE, tier=CostTier.PREMIUM)
        json_str = m.model_dump_json()
        restored = _M.model_validate_json(json_str)
        assert restored.status is AgentStatus.ACTIVE
        assert restored.tier is CostTier.PREMIUM


# ── __all__ exports ──────────────────────────────────────────────


@pytest.mark.unit
class TestCoreExports:
    def test_all_exports_importable(self) -> None:
        import ai_company.core as core_module

        for name in core_module.__all__:
            assert hasattr(core_module, name), f"{name} in __all__ but not importable"
