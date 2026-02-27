"""Tests for role and skill domain models."""

import pytest
from pydantic import ValidationError

from ai_company.core.enums import (
    DepartmentName,
    ProficiencyLevel,
    SeniorityLevel,
    SkillCategory,
)
from ai_company.core.role import Authority, CustomRole, Role, Skill

from .conftest import (
    AuthorityFactory,
    CustomRoleFactory,
    RoleFactory,
    SkillFactory,
)

# ── Skill ──────────────────────────────────────────────────────────


@pytest.mark.unit
class TestSkill:
    def test_valid_skill(self, sample_skill: Skill):
        assert sample_skill.name == "python"
        assert sample_skill.category is SkillCategory.ENGINEERING
        assert sample_skill.proficiency is ProficiencyLevel.ADVANCED

    def test_default_proficiency(self):
        skill = Skill(name="testing", category=SkillCategory.QA)
        assert skill.proficiency is ProficiencyLevel.INTERMEDIATE

    def test_empty_name_rejected(self):
        with pytest.raises(ValidationError):
            Skill(name="", category=SkillCategory.ENGINEERING)

    def test_frozen(self, sample_skill: Skill):
        with pytest.raises(ValidationError):
            sample_skill.name = "rust"  # type: ignore[misc]

    def test_json_roundtrip(self, sample_skill: Skill):
        json_str = sample_skill.model_dump_json()
        restored = Skill.model_validate_json(json_str)
        assert restored == sample_skill

    def test_factory_creates_valid_skill(self):
        skill = SkillFactory.build()
        assert isinstance(skill, Skill)
        assert len(skill.name) >= 1


# ── Authority ──────────────────────────────────────────────────────


@pytest.mark.unit
class TestAuthority:
    def test_valid_authority(self, sample_authority: Authority):
        assert sample_authority.can_approve == ("code_reviews",)
        assert sample_authority.reports_to == "engineering_lead"
        assert sample_authority.budget_limit == 5.0

    def test_defaults(self):
        auth = Authority()
        assert auth.can_approve == ()
        assert auth.reports_to is None
        assert auth.can_delegate_to == ()
        assert auth.budget_limit == 0.0

    def test_negative_budget_rejected(self):
        with pytest.raises(ValidationError):
            Authority(budget_limit=-1.0)

    def test_frozen(self, sample_authority: Authority):
        with pytest.raises(ValidationError):
            sample_authority.budget_limit = 10.0  # type: ignore[misc]

    def test_model_copy_update(self, sample_authority: Authority):
        updated = sample_authority.model_copy(update={"budget_limit": 10.0})
        assert updated.budget_limit == 10.0
        assert sample_authority.budget_limit == 5.0

    def test_factory_creates_valid_authority(self):
        auth = AuthorityFactory.build()
        assert isinstance(auth, Authority)
        assert auth.budget_limit >= 0.0


# ── Role ───────────────────────────────────────────────────────────


@pytest.mark.unit
class TestRole:
    def test_valid_role(self, sample_role: Role):
        assert sample_role.name == "Backend Developer"
        assert sample_role.department is DepartmentName.ENGINEERING
        assert "python" in sample_role.required_skills

    def test_defaults(self):
        role = Role(name="Test Role", department=DepartmentName.ENGINEERING)
        assert role.required_skills == ()
        assert role.authority_level is SeniorityLevel.MID
        assert role.tool_access == ()
        assert role.system_prompt_template is None
        assert role.description == ""

    def test_empty_name_rejected(self):
        with pytest.raises(ValidationError):
            Role(name="", department=DepartmentName.ENGINEERING)

    def test_invalid_department_rejected(self):
        with pytest.raises(ValidationError):
            Role(name="Test", department="not_a_department")  # type: ignore[arg-type]

    def test_frozen(self, sample_role: Role):
        with pytest.raises(ValidationError):
            sample_role.name = "Frontend Developer"  # type: ignore[misc]

    def test_json_roundtrip(self, sample_role: Role):
        json_str = sample_role.model_dump_json()
        restored = Role.model_validate_json(json_str)
        assert restored == sample_role

    def test_factory_creates_valid_role(self):
        role = RoleFactory.build()
        assert isinstance(role, Role)
        assert len(role.name) >= 1


# ── CustomRole ─────────────────────────────────────────────────────


@pytest.mark.unit
class TestCustomRole:
    def test_with_standard_department(self):
        role = CustomRole(
            name="Blockchain Dev",
            department=DepartmentName.ENGINEERING,
            skills=("solidity", "web3"),
        )
        assert role.department == DepartmentName.ENGINEERING

    def test_with_custom_department_string(self):
        role = CustomRole(
            name="Blockchain Dev",
            department="blockchain",
            skills=("solidity", "web3"),
        )
        assert role.department == "blockchain"

    def test_defaults(self):
        role = CustomRole(name="Test", department="custom")
        assert role.skills == ()
        assert role.authority_level is SeniorityLevel.MID
        assert role.suggested_model is None

    def test_empty_name_rejected(self):
        with pytest.raises(ValidationError):
            CustomRole(name="", department="custom")

    def test_frozen(self):
        role = CustomRole(name="Test", department="custom")
        with pytest.raises(ValidationError):
            role.name = "Changed"  # type: ignore[misc]

    def test_factory_creates_valid_custom_role(self):
        role = CustomRoleFactory.build()
        assert isinstance(role, CustomRole)
