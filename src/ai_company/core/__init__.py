"""Core domain models for the AI company framework."""

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
from ai_company.core.role import (
    Authority,
    CustomRole,
    Role,
    SeniorityInfo,
    Skill,
)
from ai_company.core.role_catalog import (
    BUILTIN_ROLES,
    SENIORITY_INFO,
    get_builtin_role,
    get_seniority_info,
)

__all__ = [
    "BUILTIN_ROLES",
    "SENIORITY_INFO",
    "AgentIdentity",
    "AgentStatus",
    "Authority",
    "Company",
    "CompanyConfig",
    "CompanyType",
    "CostTier",
    "CreativityLevel",
    "CustomRole",
    "Department",
    "DepartmentName",
    "HRRegistry",
    "MemoryConfig",
    "MemoryType",
    "ModelConfig",
    "PersonalityConfig",
    "ProficiencyLevel",
    "RiskTolerance",
    "Role",
    "SeniorityInfo",
    "SeniorityLevel",
    "Skill",
    "SkillCategory",
    "SkillSet",
    "Team",
    "ToolPermissions",
    "get_builtin_role",
    "get_seniority_info",
]
