"""Company structure and configuration models."""

from collections import Counter
from typing import Self
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ai_company.core.enums import CompanyType

_BUDGET_ROUNDING_PRECISION = 10
"""Decimal places for budget sum rounding; avoids IEEE 754 float artifacts."""


class Team(BaseModel):
    """A team within a department.

    The ``lead`` is the team's manager. The ``lead`` may also appear in
    ``members`` if they are also an individual contributor.

    Attributes:
        name: Team name.
        lead: Team lead agent name (string reference).
        members: Team member agent names.
    """

    model_config = ConfigDict(frozen=True)

    name: str = Field(min_length=1, description="Team name")
    lead: str = Field(min_length=1, description="Team lead agent name")
    members: tuple[str, ...] = Field(
        default=(),
        description="Team member agent names",
    )

    @model_validator(mode="after")
    def _validate_strings(self) -> Self:
        """Ensure no empty or whitespace-only names in identifiers and members."""
        for field_name in ("name", "lead"):
            if not getattr(self, field_name).strip():
                msg = f"{field_name} must not be whitespace-only"
                raise ValueError(msg)
        for member in self.members:
            if not member.strip():
                msg = "Empty or whitespace-only entry in members"
                raise ValueError(msg)
        if len(self.members) != len(set(self.members)):
            dupes = sorted(m for m, c in Counter(self.members).items() if c > 1)
            msg = f"Duplicate members in team {self.name!r}: {dupes}"
            raise ValueError(msg)
        return self


class Department(BaseModel):
    """An organizational department.

    Department names may be standard values from
    :class:`~ai_company.core.enums.DepartmentName` or custom names defined
    by the organization.

    Attributes:
        name: Department name (standard or custom).
        head: Department head agent name (string reference).
        budget_percent: Percentage of company budget allocated (0-100).
        teams: Teams within this department.
    """

    model_config = ConfigDict(frozen=True)

    name: str = Field(min_length=1, description="Department name")
    head: str = Field(min_length=1, description="Department head agent name")
    budget_percent: float = Field(
        default=0.0,
        ge=0.0,
        le=100.0,
        description="Percentage of company budget allocated",
    )
    teams: tuple[Team, ...] = Field(
        default=(),
        description="Teams within this department",
    )

    @model_validator(mode="after")
    def _validate_non_blank_identifiers(self) -> Self:
        """Ensure name and head are not whitespace-only."""
        for field_name in ("name", "head"):
            if not getattr(self, field_name).strip():
                msg = f"{field_name} must not be whitespace-only"
                raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _validate_unique_team_names(self) -> Self:
        """Ensure no duplicate team names within a department."""
        names = [t.name for t in self.teams]
        if len(names) != len(set(names)):
            dupes = sorted(n for n, c in Counter(names).items() if c > 1)
            msg = f"Duplicate team names in department {self.name!r}: {dupes}"
            raise ValueError(msg)
        return self


class CompanyConfig(BaseModel):
    """Company-wide configuration settings.

    Attributes:
        autonomy: Autonomy level (0 = full human oversight, 1 = fully autonomous).
        budget_monthly: Monthly budget in USD.
        communication_pattern: Default communication pattern name.
        tool_access_default: Default tool access for all agents.
    """

    model_config = ConfigDict(frozen=True)

    autonomy: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Autonomy level (0=full human oversight, 1=fully autonomous)",
    )
    budget_monthly: float = Field(
        default=100.0,
        ge=0.0,
        description="Monthly budget in USD",
    )
    communication_pattern: str = Field(
        default="hybrid",
        min_length=1,
        description="Default communication pattern",
    )
    tool_access_default: tuple[str, ...] = Field(
        default=(),
        description="Default tool access for all agents",
    )

    @model_validator(mode="after")
    def _validate_strings(self) -> Self:
        """Ensure no whitespace-only identifiers or tool access entries."""
        if not self.communication_pattern.strip():
            msg = "communication_pattern must not be whitespace-only"
            raise ValueError(msg)
        for tool in self.tool_access_default:
            if not tool.strip():
                msg = "Empty or whitespace-only entry in tool_access_default"
                raise ValueError(msg)
        return self


class HRRegistry(BaseModel):
    """Human resources registry for the company.

    ``available_roles`` and ``hiring_queue`` intentionally allow duplicate
    entries to represent multiple openings for the same role or position.

    Attributes:
        active_agents: Currently active agent names (must be unique).
        available_roles: Roles available for hiring (duplicates allowed).
        hiring_queue: Roles in the hiring pipeline (duplicates allowed).
    """

    model_config = ConfigDict(frozen=True)

    active_agents: tuple[str, ...] = Field(
        default=(),
        description="Currently active agent names",
    )
    available_roles: tuple[str, ...] = Field(
        default=(),
        description="Roles available for hiring",
    )
    hiring_queue: tuple[str, ...] = Field(
        default=(),
        description="Roles in the hiring pipeline",
    )

    @model_validator(mode="after")
    def _validate_entries(self) -> Self:
        """Ensure no empty strings and no duplicate entries in active_agents."""
        for field_name in ("active_agents", "available_roles", "hiring_queue"):
            for value in getattr(self, field_name):
                if not value.strip():
                    msg = f"Empty or whitespace-only entry in {field_name}"
                    raise ValueError(msg)
        agents = self.active_agents
        if len(agents) != len(set(agents)):
            dupes = sorted(a for a, c in Counter(agents).items() if c > 1)
            msg = f"Duplicate entries in active_agents: {dupes}"
            raise ValueError(msg)
        return self


class Company(BaseModel):
    """Top-level company entity.

    Validates that department names are unique and that budget allocations
    do not exceed 100%. The sum may be less than 100% to allow for an
    unallocated reserve.

    Attributes:
        id: Company identifier.
        name: Company name.
        type: Company template type.
        departments: Company departments.
        config: Company-wide configuration.
        hr_registry: HR registry.
    """

    model_config = ConfigDict(frozen=True)

    id: UUID = Field(default_factory=uuid4, description="Company identifier")
    name: str = Field(min_length=1, description="Company name")
    type: CompanyType = Field(
        default=CompanyType.CUSTOM,
        description="Company template type",
    )
    departments: tuple[Department, ...] = Field(
        default=(),
        description="Company departments",
    )
    config: CompanyConfig = Field(
        default_factory=CompanyConfig,
        description="Company-wide configuration",
    )
    hr_registry: HRRegistry = Field(
        default_factory=HRRegistry,
        description="HR registry",
    )

    @model_validator(mode="after")
    def _validate_non_blank_name(self) -> Self:
        """Ensure company name is not whitespace-only."""
        if not self.name.strip():
            msg = "name must not be whitespace-only"
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _validate_departments(self) -> Self:
        """Validate department names are unique and budgets do not exceed 100%."""
        # Unique department names
        names = [d.name for d in self.departments]
        if len(names) != len(set(names)):
            dupes = sorted(n for n, c in Counter(names).items() if c > 1)
            msg = f"Duplicate department names: {dupes}"
            raise ValueError(msg)

        # Budget sum
        max_budget_percent = 100.0
        total = sum(d.budget_percent for d in self.departments)
        if round(total, _BUDGET_ROUNDING_PRECISION) > max_budget_percent:
            msg = (
                f"Department budget allocations sum to {total:.2f}%, "
                f"exceeding {max_budget_percent:.0f}%"
            )
            raise ValueError(msg)
        return self
