"""Request/response models for the first-run setup controller."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator

from synthorg.core.enums import SeniorityLevel, SkillPattern
from synthorg.core.types import NotBlankStr  # noqa: TC001
from synthorg.templates.model_requirements import ModelTier  # noqa: TC001


class SetupStatusResponse(BaseModel):
    """First-run setup status.

    Attributes:
        needs_admin: True if no user with the CEO role exists yet.
        needs_setup: True if setup has not been completed.
        has_providers: True if at least one provider is configured.
        has_name_locales: True if name locale preferences have been configured.
        has_company: True if a company name has been set.
        has_agents: True if at least one agent has been created.
        min_password_length: Backend-configured minimum password length.
    """

    model_config = ConfigDict(frozen=True)

    needs_admin: bool
    needs_setup: bool
    has_providers: bool
    has_name_locales: bool
    has_company: bool
    has_agents: bool
    min_password_length: int = Field(ge=8)


class TemplateInfoResponse(BaseModel):
    """Summary of an available company template.

    Attributes:
        name: Template identifier.
        display_name: Human-readable name.
        description: Short description.
        source: Where the template was found (builtin or user).
        tags: Free-form categorization tags for template filtering and discovery.
        skill_patterns: Skill design pattern identifiers describing how the
            template's agents interact (e.g. ``"tool_wrapper"``, ``"pipeline"``).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: NotBlankStr
    display_name: NotBlankStr
    description: str
    source: Literal["builtin", "user"]
    tags: tuple[NotBlankStr, ...] = Field(
        default=(),
        description="Categorization tags for filtering and discovery",
    )
    skill_patterns: tuple[SkillPattern, ...] = Field(
        default=(),
        description="Skill design pattern identifiers",
    )


class SetupCompanyRequest(BaseModel):
    """Company creation payload for first-run setup.

    Attributes:
        company_name: Company display name.
        description: Optional company description.
        template_name: Optional template to apply (None = blank company).
    """

    model_config = ConfigDict(frozen=True)

    company_name: NotBlankStr = Field(max_length=200)
    description: str | None = Field(default=None, max_length=1000)
    template_name: NotBlankStr | None = Field(default=None, max_length=100)


class SetupAgentSummary(BaseModel):
    """Summary of an agent for the Review Org step.

    Attributes:
        name: Agent display name.
        role: Agent role.
        department: Assigned department.
        level: Seniority level string.
        model_provider: LLM provider name (empty if unassigned).
        model_id: Model identifier (empty if unassigned).
        tier: Original tier requirement from the template.
        personality_preset: Personality preset name, if any.
    """

    model_config = ConfigDict(frozen=True)

    name: NotBlankStr
    role: NotBlankStr
    department: NotBlankStr
    level: str = ""
    model_provider: str = ""
    model_id: str = ""
    tier: ModelTier = "medium"
    personality_preset: NotBlankStr | None = None


class SetupCompanyResponse(BaseModel):
    """Company creation result.

    Attributes:
        company_name: The company name that was set.
        description: The company description that was set, if any.
        template_applied: Name of the template that was applied, if any.
        department_count: Number of departments created.
        agent_count: Number of agents auto-created from template
            (computed from ``agents``).
        agents: Agent summaries for the Review Org step.
    """

    model_config = ConfigDict(frozen=True)

    company_name: NotBlankStr
    description: str | None
    template_applied: NotBlankStr | None
    department_count: int = Field(ge=0)
    agents: tuple[SetupAgentSummary, ...] = ()

    @computed_field  # type: ignore[prop-decorator]
    @property
    def agent_count(self) -> int:
        """Number of agents auto-created from template."""
        return len(self.agents)


class SetupAgentRequest(BaseModel):
    """Agent creation payload for first-run setup.

    Attributes:
        name: Agent display name.
        role: Agent role name.
        level: Seniority level.
        personality_preset: Personality preset name.
        model_provider: Provider name for the agent's model.
        model_id: Model identifier from that provider.
        department: Department to assign the agent to.
        budget_limit_monthly: Optional monthly budget limit in USD (base currency).
    """

    model_config = ConfigDict(frozen=True)

    name: NotBlankStr = Field(max_length=200)
    role: NotBlankStr = Field(max_length=100)
    level: SeniorityLevel = Field(default=SeniorityLevel.MID)
    personality_preset: NotBlankStr = Field(
        default="pragmatic_builder",
        max_length=100,
    )
    model_provider: NotBlankStr = Field(max_length=100)
    model_id: NotBlankStr = Field(max_length=200)
    department: NotBlankStr = Field(default="engineering", max_length=100)
    budget_limit_monthly: float | None = Field(default=None, ge=0.0, le=1_000_000.0)

    @model_validator(mode="before")
    @classmethod
    def _validate_preset_exists(cls, values: dict[str, Any]) -> dict[str, Any]:
        """Normalize and validate the personality preset before construction."""
        from synthorg.templates.presets import PERSONALITY_PRESETS  # noqa: PLC0415

        raw = values.get("personality_preset", "pragmatic_builder")
        key = str(raw).strip().lower() if raw else "pragmatic_builder"
        if key not in PERSONALITY_PRESETS:
            available = sorted(PERSONALITY_PRESETS)
            msg = f"Unknown personality preset {raw!r}. Available: {available}"
            raise ValueError(msg)
        values["personality_preset"] = key
        return values


class SetupAgentResponse(BaseModel):
    """Agent creation result.

    Attributes:
        name: Agent display name.
        role: Agent role.
        department: Assigned department.
        model_provider: LLM provider name.
        model_id: Model identifier.
    """

    model_config = ConfigDict(frozen=True)

    name: NotBlankStr
    role: NotBlankStr
    department: NotBlankStr
    model_provider: NotBlankStr
    model_id: NotBlankStr


class UpdateAgentModelRequest(BaseModel):
    """Request to update an agent's model assignment during setup.

    Attributes:
        model_provider: Provider name.
        model_id: Model identifier from that provider.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    model_provider: NotBlankStr = Field(max_length=100)
    model_id: NotBlankStr = Field(max_length=200)


class UpdateAgentNameRequest(BaseModel):
    """Request to update an agent's display name during setup.

    Attributes:
        name: New agent display name.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: NotBlankStr = Field(max_length=200)


class SetupAgentsListResponse(BaseModel):
    """List of agents currently configured in setup.

    Attributes:
        agents: Agent summaries.
        agent_count: Number of agents (computed from ``agents``).
    """

    model_config = ConfigDict(frozen=True)

    agents: tuple[SetupAgentSummary, ...]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def agent_count(self) -> int:
        """Number of agents currently configured."""
        return len(self.agents)


class SetupNameLocalesRequest(BaseModel):
    """Name locale selection payload.

    Attributes:
        locales: List of Faker locale codes (1--100 entries), or
            ``["__all__"]`` for all Latin-script locales.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    locales: list[NotBlankStr] = Field(min_length=1, max_length=100)


class SetupNameLocalesResponse(BaseModel):
    """Current name locale configuration.

    Attributes:
        locales: Stored locale codes (``["__all__"]`` if worldwide).
    """

    model_config = ConfigDict(frozen=True)

    locales: list[NotBlankStr]


class AvailableLocalesResponse(BaseModel):
    """Available locales grouped by region.

    Attributes:
        regions: Mapping of region display name to locale codes.
        display_names: Mapping of locale code to human-readable name.
    """

    model_config = ConfigDict(frozen=True)

    regions: dict[str, list[str]]
    display_names: dict[str, str]


class SetupCompleteResponse(BaseModel):
    """Setup completion result.

    Attributes:
        setup_complete: Always True on success.
    """

    model_config = ConfigDict(frozen=True)

    setup_complete: Literal[True]
