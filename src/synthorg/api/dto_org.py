"""Request DTOs for company, department, and agent mutation endpoints."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from synthorg.core.enums import AgentStatus, AutonomyLevel, SeniorityLevel
from synthorg.core.types import NotBlankStr  # noqa: TC001

# ── Company ──────────────────────���───────────────────────────


class UpdateCompanyRequest(BaseModel):
    """Partial update for company-level settings."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    company_name: NotBlankStr | None = None
    autonomy_level: AutonomyLevel | None = None
    budget_monthly: float | None = Field(default=None, gt=0)
    communication_pattern: NotBlankStr | None = None


# ── Departments ──────────────────────────────────────────────


class CreateDepartmentRequest(BaseModel):
    """Request body for creating a new department."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    name: NotBlankStr = Field(max_length=128)
    display_name: NotBlankStr = Field(max_length=256)
    head: NotBlankStr | None = None
    budget_percent: float = Field(default=0.0, ge=0.0, le=100.0)
    autonomy_level: AutonomyLevel | None = None


class UpdateDepartmentRequest(BaseModel):
    """Partial update for an existing department."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    display_name: NotBlankStr | None = Field(default=None, max_length=256)
    head: str | None = None
    budget_percent: float | None = Field(default=None, ge=0.0, le=100.0)
    autonomy_level: AutonomyLevel | None = None
    teams: tuple[dict[str, Any], ...] | None = None
    ceremony_policy: dict[str, Any] | None = None


class ReorderDepartmentsRequest(BaseModel):
    """Reorder departments -- must be an exact permutation."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    department_names: tuple[NotBlankStr, ...] = Field(min_length=1)


# ── Agents ────────────────────────────────────────��──────────


class CreateAgentOrgRequest(BaseModel):
    """Request body for creating a new agent in the org config."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    name: NotBlankStr = Field(max_length=128)
    role: NotBlankStr = Field(max_length=128)
    department: NotBlankStr = Field(max_length=128)
    level: SeniorityLevel = SeniorityLevel.MID
    personality_preset: NotBlankStr | None = None
    model_provider: NotBlankStr | None = None
    model_id: NotBlankStr | None = None


class UpdateAgentOrgRequest(BaseModel):
    """Partial update for an existing agent in the org config."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    name: NotBlankStr | None = Field(default=None, max_length=128)
    role: NotBlankStr | None = Field(default=None, max_length=128)
    department: NotBlankStr | None = Field(default=None, max_length=128)
    level: SeniorityLevel | None = None
    status: AgentStatus | None = None
    autonomy_level: AutonomyLevel | None = None


class ReorderAgentsRequest(BaseModel):
    """Reorder agents within a department -- must be an exact permutation."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    agent_names: tuple[NotBlankStr, ...] = Field(min_length=1)
