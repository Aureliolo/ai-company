"""Company structure and configuration models."""

from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ai_company.core.enums import CompanyType


class Team(BaseModel):
    """A team within a department.

    The ``lead`` is the team's manager and is not required to appear in
    ``members``.  ``members`` lists the individual contributors on the team.

    Attributes:
        name: Team name.
        lead: Team lead agent name (string reference).
        members: Team member agent names (excluding the lead).
    """

    model_config = ConfigDict(frozen=True)

    name: str = Field(min_length=1, description="Team name")
    lead: str = Field(min_length=1, description="Team lead agent name")
    members: tuple[str, ...] = Field(
        default=(),
        description="Team member agent names",
    )


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
    def _validate_unique_team_names(self) -> Department:
        """Ensure no duplicate team names within a department."""
        names = [t.name for t in self.teams]
        if len(names) != len(set(names)):
            dupes = sorted({n for n in names if names.count(n) > 1})
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


class HRRegistry(BaseModel):
    """Human resources registry for the company.

    Attributes:
        active_agents: Currently active agent names.
        available_roles: Roles available for hiring.
        hiring_queue: Roles in the hiring pipeline.
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
    def _validate_no_duplicate_agents(self) -> HRRegistry:
        """Ensure no duplicate entries in active_agents."""
        agents = self.active_agents
        if len(agents) != len(set(agents)):
            dupes = sorted({a for a in agents if agents.count(a) > 1})
            msg = f"Duplicate entries in active_agents: {dupes}"
            raise ValueError(msg)
        return self


class Company(BaseModel):
    """Top-level company entity.

    Validates that department budget allocations do not exceed 100%.
    The sum may be less than 100% to allow for an unallocated reserve.

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
    def _validate_departments(self) -> Company:
        """Validate department names are unique and budgets do not exceed 100%."""
        # Unique department names
        names = [d.name for d in self.departments]
        if len(names) != len(set(names)):
            dupes = sorted({n for n in names if names.count(n) > 1})
            msg = f"Duplicate department names: {dupes}"
            raise ValueError(msg)

        # Budget sum (round to 10 decimals to avoid float artifacts)
        max_budget_percent = 100.0
        total = sum(d.budget_percent for d in self.departments)
        if round(total, 10) > max_budget_percent:
            msg = (
                f"Department budget allocations sum to {total:.2f}%, "
                f"exceeding {max_budget_percent:.0f}%"
            )
            raise ValueError(msg)
        return self
