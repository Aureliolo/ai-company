"""Tests for core domain enumerations."""

import pytest

from ai_company.core.enums import (
    AgentStatus,
    CompanyType,
    CostTier,
    CreativityLevel,
    DepartmentName,
    MemoryType,
    ProficiencyLevel,
    RiskTolerance,
    SeniorityLevel,
    SkillCategory,
)

# ── Member Counts ──────────────────────────────────────────────────


@pytest.mark.unit
class TestEnumMemberCounts:
    def test_seniority_level_has_8_members(self):
        assert len(SeniorityLevel) == 8

    def test_agent_status_has_3_members(self):
        assert len(AgentStatus) == 3

    def test_risk_tolerance_has_3_members(self):
        assert len(RiskTolerance) == 3

    def test_creativity_level_has_3_members(self):
        assert len(CreativityLevel) == 3

    def test_memory_type_has_4_members(self):
        assert len(MemoryType) == 4

    def test_cost_tier_has_4_members(self):
        assert len(CostTier) == 4

    def test_company_type_has_8_members(self):
        assert len(CompanyType) == 8

    def test_skill_category_has_9_members(self):
        assert len(SkillCategory) == 9

    def test_proficiency_level_has_4_members(self):
        assert len(ProficiencyLevel) == 4

    def test_department_name_has_9_members(self):
        assert len(DepartmentName) == 9


# ── String Values ──────────────────────────────────────────────────


@pytest.mark.unit
class TestEnumStringValues:
    def test_seniority_levels_are_lowercase(self):
        for member in SeniorityLevel:
            assert member.value == member.value.lower()

    def test_agent_status_values(self):
        assert AgentStatus.ACTIVE == "active"
        assert AgentStatus.ON_LEAVE == "on_leave"
        assert AgentStatus.TERMINATED == "terminated"

    def test_cost_tier_values(self):
        assert CostTier.LOW == "low"
        assert CostTier.MEDIUM == "medium"
        assert CostTier.HIGH == "high"
        assert CostTier.PREMIUM == "premium"

    def test_company_type_values(self):
        assert CompanyType.SOLO_FOUNDER == "solo_founder"
        assert CompanyType.STARTUP == "startup"
        assert CompanyType.CUSTOM == "custom"


# ── StrEnum Behavior ───────────────────────────────────────────────


@pytest.mark.unit
class TestStrEnumBehavior:
    def test_strenum_is_string(self):
        assert isinstance(SeniorityLevel.JUNIOR, str)

    def test_strenum_equality_with_string(self):
        assert SeniorityLevel.JUNIOR == "junior"

    def test_strenum_iteration(self):
        levels = list(SeniorityLevel)
        assert len(levels) == 8
        assert levels[0] == SeniorityLevel.JUNIOR

    def test_strenum_membership(self):
        assert "senior" in [m.value for m in SeniorityLevel]

    def test_strenum_from_value(self):
        assert SeniorityLevel("junior") is SeniorityLevel.JUNIOR

    def test_strenum_invalid_value_raises(self):
        with pytest.raises(ValueError, match="not_a_level"):
            SeniorityLevel("not_a_level")


# ── Pydantic Integration ──────────────────────────────────────────


@pytest.mark.unit
class TestEnumPydanticIntegration:
    def test_enum_serializes_as_string(self):
        from pydantic import BaseModel

        class _M(BaseModel):
            level: SeniorityLevel

        m = _M(level=SeniorityLevel.SENIOR)
        dumped = m.model_dump()
        assert dumped["level"] == "senior"

    def test_enum_deserializes_from_string(self):
        from pydantic import BaseModel

        class _M(BaseModel):
            level: SeniorityLevel

        m = _M.model_validate({"level": "senior"})
        assert m.level is SeniorityLevel.SENIOR

    def test_enum_invalid_value_rejected(self):
        from pydantic import BaseModel, ValidationError

        class _M(BaseModel):
            level: SeniorityLevel

        with pytest.raises(ValidationError):
            _M.model_validate({"level": "invalid"})

    def test_enum_json_roundtrip(self):
        from pydantic import BaseModel

        class _M(BaseModel):
            status: AgentStatus
            tier: CostTier

        m = _M(status=AgentStatus.ACTIVE, tier=CostTier.PREMIUM)
        json_str = m.model_dump_json()
        restored = _M.model_validate_json(json_str)
        assert restored.status is AgentStatus.ACTIVE
        assert restored.tier is CostTier.PREMIUM
