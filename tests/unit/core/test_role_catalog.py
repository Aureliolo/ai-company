"""Tests for the built-in role catalog and seniority mappings."""

from unittest.mock import patch

import pytest
from pydantic import ValidationError

from ai_company.core.enums import (
    CostTier,
    DepartmentName,
    SeniorityLevel,
)
from ai_company.core.role import Role, SeniorityInfo
from ai_company.core.role_catalog import (
    BUILTIN_ROLES,
    SENIORITY_INFO,
    get_builtin_role,
    get_seniority_info,
)

# ── Seniority Info ─────────────────────────────────────────────────


@pytest.mark.unit
class TestSeniorityInfo:
    def test_has_8_entries(self) -> None:
        assert len(SENIORITY_INFO) == 8

    def test_covers_all_seniority_levels(self) -> None:
        levels = {info.level for info in SENIORITY_INFO}
        expected = set(SeniorityLevel)
        assert levels == expected

    def test_no_duplicate_levels(self) -> None:
        levels = [info.level for info in SENIORITY_INFO]
        assert len(levels) == len(set(levels))

    def test_all_entries_are_seniority_info(self) -> None:
        for info in SENIORITY_INFO:
            assert isinstance(info, SeniorityInfo)

    def test_junior_is_low_cost(self) -> None:
        info = get_seniority_info(SeniorityLevel.JUNIOR)
        assert info.cost_tier == CostTier.LOW

    def test_c_suite_is_premium_cost(self) -> None:
        info = get_seniority_info(SeniorityLevel.C_SUITE)
        assert info.cost_tier == CostTier.PREMIUM

    def test_senior_uses_sonnet_tier(self) -> None:
        info = get_seniority_info(SeniorityLevel.SENIOR)
        assert info.typical_model_tier == "sonnet"

    def test_all_entries_frozen(self) -> None:
        for info in SENIORITY_INFO:
            with pytest.raises(ValidationError):
                info.level = SeniorityLevel.JUNIOR  # type: ignore[misc]


# ── Builtin Roles ─────────────────────────────────────────────────


@pytest.mark.unit
class TestBuiltinRoles:
    def test_has_31_roles(self) -> None:
        assert len(BUILTIN_ROLES) == 31

    def test_all_entries_are_role(self) -> None:
        for role in BUILTIN_ROLES:
            assert isinstance(role, Role)

    def test_no_duplicate_names(self) -> None:
        names = [r.name for r in BUILTIN_ROLES]
        assert len(names) == len(set(names))

    def test_all_departments_represented(self) -> None:
        departments = {r.department for r in BUILTIN_ROLES}
        expected = set(DepartmentName)
        assert departments == expected

    def test_c_suite_roles_present(self) -> None:
        c_suite = [
            r for r in BUILTIN_ROLES if r.authority_level is SeniorityLevel.C_SUITE
        ]
        names = {r.name for r in c_suite}
        assert {"CEO", "CTO", "CFO", "COO", "CPO"}.issubset(names)

    def test_all_roles_have_description(self) -> None:
        for role in BUILTIN_ROLES:
            assert role.description, f"{role.name} has no description"

    def test_all_roles_have_required_skills(self) -> None:
        for role in BUILTIN_ROLES:
            assert len(role.required_skills) > 0, f"{role.name} has no required_skills"

    def test_all_roles_frozen(self) -> None:
        for role in BUILTIN_ROLES:
            with pytest.raises(ValidationError):
                role.name = "Changed"  # type: ignore[misc]


# ── Lookup Functions ───────────────────────────────────────────────


@pytest.mark.unit
class TestGetBuiltinRole:
    def test_exact_match(self) -> None:
        role = get_builtin_role("CEO")
        assert role is not None
        assert role.name == "CEO"

    def test_case_insensitive(self) -> None:
        role = get_builtin_role("ceo")
        assert role is not None
        assert role.name == "CEO"

    def test_mixed_case(self) -> None:
        role = get_builtin_role("Backend Developer")
        assert role is not None
        assert role.name == "Backend Developer"

    def test_not_found_returns_none(self) -> None:
        assert get_builtin_role("Nonexistent Role") is None

    def test_empty_string_returns_none(self) -> None:
        assert get_builtin_role("") is None

    def test_whitespace_stripped(self) -> None:
        role = get_builtin_role("  CEO  ")
        assert role is not None
        assert role.name == "CEO"

    def test_whitespace_only_returns_none(self) -> None:
        assert get_builtin_role("   ") is None

    @pytest.mark.parametrize(
        "name",
        [
            "CEO",
            "CTO",
            "CFO",
            "COO",
            "CPO",
            "Product Manager",
            "UX Designer",
            "UI Designer",
            "UX Researcher",
            "Technical Writer",
            "Software Architect",
            "Frontend Developer",
            "Backend Developer",
            "Full-Stack Developer",
            "DevOps/SRE Engineer",
            "Database Engineer",
            "Security Engineer",
            "QA Lead",
            "QA Engineer",
            "Automation Engineer",
            "Performance Engineer",
            "Data Analyst",
            "Data Engineer",
            "ML Engineer",
            "Project Manager",
            "Scrum Master",
            "HR Manager",
            "Security Operations",
            "Content Writer",
            "Brand Strategist",
            "Growth Marketer",
        ],
    )
    def test_all_roles_lookupable(self, name: str) -> None:
        role = get_builtin_role(name)
        assert role is not None, f"Role {name!r} not found in catalog"
        assert role.name == name


@pytest.mark.unit
class TestGetSeniorityInfo:
    def test_found(self) -> None:
        info = get_seniority_info(SeniorityLevel.SENIOR)
        assert info.level is SeniorityLevel.SENIOR

    @pytest.mark.parametrize("level", list(SeniorityLevel))
    def test_all_levels_lookupable(self, level: SeniorityLevel) -> None:
        info = get_seniority_info(level)
        assert info.level is level

    def test_raises_lookup_error_for_missing_level(self) -> None:
        with (
            patch.dict(
                "ai_company.core.role_catalog._SENIORITY_INFO_BY_LEVEL",
                {},
                clear=True,
            ),
            pytest.raises(LookupError, match="catalog may be incomplete"),
        ):
            get_seniority_info(SeniorityLevel.JUNIOR)
