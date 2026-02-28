"""Root configuration schema and config-level Pydantic models."""

from collections import Counter
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ai_company.budget.config import BudgetConfig
from ai_company.communication.config import CommunicationConfig
from ai_company.core.company import CompanyConfig, Department
from ai_company.core.enums import CompanyType, SeniorityLevel
from ai_company.core.role import CustomRole  # noqa: TC001
from ai_company.observability.config import LogConfig  # noqa: TC001


class ProviderModelConfig(BaseModel):
    """Configuration for a single LLM model within a provider.

    Attributes:
        id: Model identifier (e.g. ``"claude-sonnet-4-6"``).
        alias: Short alias for referencing this model in routing rules.
        cost_per_1k_input: Cost per 1 000 input tokens in USD.
        cost_per_1k_output: Cost per 1 000 output tokens in USD.
        max_context: Maximum context window size in tokens.
    """

    model_config = ConfigDict(frozen=True)

    id: str = Field(min_length=1, description="Model identifier")
    alias: str | None = Field(
        default=None,
        min_length=1,
        description="Short alias for routing rules",
    )
    cost_per_1k_input: float = Field(
        default=0.0,
        ge=0.0,
        description="Cost per 1k input tokens in USD",
    )
    cost_per_1k_output: float = Field(
        default=0.0,
        ge=0.0,
        description="Cost per 1k output tokens in USD",
    )
    max_context: int = Field(
        default=200_000,
        gt=0,
        description="Maximum context window size in tokens",
    )

    @model_validator(mode="after")
    def _validate_non_blank_strings(self) -> Self:
        """Ensure identifier fields are not whitespace-only."""
        if not self.id.strip():
            msg = "id must not be whitespace-only"
            raise ValueError(msg)
        if self.alias is not None and not self.alias.strip():
            msg = "alias must not be whitespace-only"
            raise ValueError(msg)
        return self


class ProviderConfig(BaseModel):
    """Configuration for an LLM provider.

    Attributes:
        api_key: API key (typically injected by secret management).
        base_url: Base URL for the provider API.
        models: Available models for this provider.
    """

    model_config = ConfigDict(frozen=True)

    api_key: str | None = Field(
        default=None,
        description="API key",
    )
    base_url: str | None = Field(
        default=None,
        min_length=1,
        description="Base URL for the provider API",
    )
    models: tuple[ProviderModelConfig, ...] = Field(
        default=(),
        description="Available models",
    )

    @model_validator(mode="after")
    def _validate_non_blank_strings(self) -> Self:
        """Ensure optional string fields are not whitespace-only."""
        if self.api_key is not None and not self.api_key.strip():
            msg = "api_key must not be whitespace-only"
            raise ValueError(msg)
        if self.base_url is not None and not self.base_url.strip():
            msg = "base_url must not be whitespace-only"
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _validate_unique_model_identifiers(self) -> Self:
        """Ensure model IDs and aliases are each unique."""
        ids = [m.id for m in self.models]
        if len(ids) != len(set(ids)):
            dupes = sorted(i for i, c in Counter(ids).items() if c > 1)
            msg = f"Duplicate model IDs: {dupes}"
            raise ValueError(msg)
        aliases = [m.alias for m in self.models if m.alias is not None]
        if len(aliases) != len(set(aliases)):
            dupes = sorted(a for a, c in Counter(aliases).items() if c > 1)
            msg = f"Duplicate model aliases: {dupes}"
            raise ValueError(msg)
        return self


class RoutingRuleConfig(BaseModel):
    """A single model routing rule.

    Attributes:
        role_level: Seniority level this rule applies to.
        task_type: Task type this rule applies to.
        preferred_model: Preferred model alias or ID.
        fallback: Fallback model alias or ID.
    """

    model_config = ConfigDict(frozen=True)

    role_level: SeniorityLevel | None = Field(
        default=None,
        description="Seniority level filter",
    )
    task_type: str | None = Field(
        default=None,
        min_length=1,
        description="Task type filter",
    )
    preferred_model: str = Field(
        min_length=1,
        description="Preferred model alias or ID",
    )
    fallback: str | None = Field(
        default=None,
        min_length=1,
        description="Fallback model alias or ID",
    )

    @model_validator(mode="after")
    def _validate_non_blank_strings(self) -> Self:
        """Ensure string fields are not whitespace-only."""
        if not self.preferred_model.strip():
            msg = "preferred_model must not be whitespace-only"
            raise ValueError(msg)
        if self.task_type is not None and not self.task_type.strip():
            msg = "task_type must not be whitespace-only"
            raise ValueError(msg)
        if self.fallback is not None and not self.fallback.strip():
            msg = "fallback must not be whitespace-only"
            raise ValueError(msg)
        return self


class RoutingConfig(BaseModel):
    """Model routing configuration.

    Attributes:
        strategy: Routing strategy name (e.g. ``"cost_aware"``).
        rules: Ordered routing rules.
        fallback_chain: Ordered fallback model aliases or IDs.
    """

    model_config = ConfigDict(frozen=True)

    strategy: str = Field(
        default="cost_aware",
        min_length=1,
        description="Routing strategy name",
    )
    rules: tuple[RoutingRuleConfig, ...] = Field(
        default=(),
        description="Ordered routing rules",
    )
    fallback_chain: tuple[str, ...] = Field(
        default=(),
        description="Ordered fallback model aliases or IDs",
    )

    @model_validator(mode="after")
    def _validate_non_blank_strings(self) -> Self:
        """Ensure strategy and fallback entries are not whitespace-only."""
        if not self.strategy.strip():
            msg = "strategy must not be whitespace-only"
            raise ValueError(msg)
        for entry in self.fallback_chain:
            if not entry.strip():
                msg = "Empty or whitespace-only entry in fallback_chain"
                raise ValueError(msg)
        return self


class AgentConfig(BaseModel):
    """Agent configuration from YAML.

    Uses raw dicts for personality, model, memory, tools, and authority
    because :class:`~ai_company.core.agent.AgentIdentity` has runtime
    fields (``id``, ``hiring_date``, ``status``) that are not present in
    config.  The engine constructs full ``AgentIdentity`` objects at
    startup.

    Attributes:
        name: Agent display name.
        role: Role name.
        department: Department name.
        level: Seniority level.
        personality: Raw personality config dict.
        model: Raw model config dict.
        memory: Raw memory config dict.
        tools: Raw tools config dict.
        authority: Raw authority config dict.
    """

    model_config = ConfigDict(frozen=True)

    name: str = Field(min_length=1, description="Agent display name")
    role: str = Field(min_length=1, description="Role name")
    department: str = Field(min_length=1, description="Department name")
    level: SeniorityLevel = Field(
        default=SeniorityLevel.MID,
        description="Seniority level",
    )
    personality: dict[str, Any] = Field(
        default_factory=dict,
        description="Raw personality config",
    )
    model: dict[str, Any] = Field(
        default_factory=dict,
        description="Raw model config",
    )
    memory: dict[str, Any] = Field(
        default_factory=dict,
        description="Raw memory config",
    )
    tools: dict[str, Any] = Field(
        default_factory=dict,
        description="Raw tools config",
    )
    authority: dict[str, Any] = Field(
        default_factory=dict,
        description="Raw authority config",
    )

    @model_validator(mode="after")
    def _validate_non_blank_identifiers(self) -> Self:
        """Ensure name, role, and department are not whitespace-only."""
        for field_name in ("name", "role", "department"):
            if not getattr(self, field_name).strip():
                msg = f"{field_name} must not be whitespace-only"
                raise ValueError(msg)
        return self


class RootConfig(BaseModel):
    """Root company configuration — the top-level validation target.

    Aggregates all sub-configurations into a single frozen model that
    represents a fully validated company setup.

    Attributes:
        company_name: Company name (required).
        company_type: Company template type.
        departments: Organizational departments.
        agents: Agent configurations.
        custom_roles: User-defined custom roles.
        config: Company-wide settings.
        budget: Budget configuration.
        communication: Communication configuration.
        providers: LLM provider configurations keyed by provider name.
        routing: Model routing configuration.
        logging: Logging configuration (``None`` to use platform defaults).
    """

    model_config = ConfigDict(frozen=True)

    company_name: str = Field(
        min_length=1,
        description="Company name",
    )
    company_type: CompanyType = Field(
        default=CompanyType.CUSTOM,
        description="Company template type",
    )
    departments: tuple[Department, ...] = Field(
        default=(),
        description="Organizational departments",
    )
    agents: tuple[AgentConfig, ...] = Field(
        default=(),
        description="Agent configurations",
    )
    custom_roles: tuple[CustomRole, ...] = Field(
        default=(),
        description="User-defined custom roles",
    )
    config: CompanyConfig = Field(
        default_factory=CompanyConfig,
        description="Company-wide settings",
    )
    budget: BudgetConfig = Field(
        default_factory=BudgetConfig,
        description="Budget configuration",
    )
    communication: CommunicationConfig = Field(
        default_factory=CommunicationConfig,
        description="Communication configuration",
    )
    providers: dict[str, ProviderConfig] = Field(
        default_factory=dict,
        description="LLM provider configurations",
    )
    routing: RoutingConfig = Field(
        default_factory=RoutingConfig,
        description="Model routing configuration",
    )
    logging: LogConfig | None = Field(
        default=None,
        description="Logging configuration",
    )

    @model_validator(mode="after")
    def _validate_company_name_not_blank(self) -> Self:
        """Ensure company name is not whitespace-only."""
        if not self.company_name.strip():
            msg = "company_name must not be whitespace-only"
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _validate_unique_agent_names(self) -> Self:
        """Ensure agent names are unique."""
        names = [a.name for a in self.agents]
        if len(names) != len(set(names)):
            dupes = sorted(n for n, c in Counter(names).items() if c > 1)
            msg = f"Duplicate agent names: {dupes}"
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _validate_unique_department_names(self) -> Self:
        """Ensure department names are unique."""
        names = [d.name for d in self.departments]
        if len(names) != len(set(names)):
            dupes = sorted(n for n, c in Counter(names).items() if c > 1)
            msg = f"Duplicate department names: {dupes}"
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _validate_routing_references(self) -> Self:
        """Ensure routing model references exist in provider configs."""
        if not self.routing.rules and not self.routing.fallback_chain:
            return self

        known_models: set[str] = set()
        for provider in self.providers.values():
            for model in provider.models:
                known_models.add(model.id)
                if model.alias:
                    known_models.add(model.alias)

        for rule in self.routing.rules:
            if rule.preferred_model not in known_models:
                msg = f"Routing rule references unknown model: {rule.preferred_model!r}"
                raise ValueError(msg)
            if rule.fallback and rule.fallback not in known_models:
                msg = f"Routing rule references unknown fallback: {rule.fallback!r}"
                raise ValueError(msg)

        for model_ref in self.routing.fallback_chain:
            if model_ref not in known_models:
                msg = f"Routing fallback_chain references unknown model: {model_ref!r}"
                raise ValueError(msg)
        return self
