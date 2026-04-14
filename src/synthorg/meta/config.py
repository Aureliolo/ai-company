"""Configuration for the self-improving company meta-loop.

Defines frozen Pydantic config models with safe defaults:
disabled by default, mandatory approval gate, conservative
thresholds.
"""

from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from synthorg.core.types import NotBlankStr
from synthorg.meta.models import EvolutionMode, RolloutStrategyType
from synthorg.observability import get_logger

logger = get_logger(__name__)


class RuleConfig(BaseModel):
    """Configuration for the signal rule engine.

    Attributes:
        disabled_rules: Names of built-in rules to disable.
        custom_rule_modules: Dotted module paths for user-defined rules.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    disabled_rules: tuple[NotBlankStr, ...] = ()
    custom_rule_modules: tuple[NotBlankStr, ...] = ()


class RolloutConfig(BaseModel):
    """Configuration for proposal rollout behavior.

    Attributes:
        default_strategy: Default rollout strategy for proposals.
        observation_window_hours: Post-apply observation window.
        regression_check_interval_hours: How often to check for
            regression during the observation window.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    default_strategy: RolloutStrategyType = RolloutStrategyType.BEFORE_AFTER
    observation_window_hours: int = Field(default=48, ge=1)
    regression_check_interval_hours: int = Field(default=4, ge=1)

    @model_validator(mode="after")
    def _validate_interval_within_window(self) -> Self:
        """Regression check interval must fit within observation window."""
        if self.regression_check_interval_hours > self.observation_window_hours:
            msg = "regression_check_interval_hours must be <= observation_window_hours"
            raise ValueError(msg)
        return self


class RegressionConfig(BaseModel):
    """Configuration for regression detection thresholds.

    All values are fractional (0.10 = 10% degradation). Layer 1
    (threshold) fires instantly; layer 2 (statistical) fires after
    the observation window completes.

    Attributes:
        quality_drop_threshold: Max quality score drop (layer 1).
        cost_increase_threshold: Max cost increase (layer 1).
        error_rate_increase_threshold: Max error rate increase (layer 1).
        success_rate_drop_threshold: Max success rate drop (layer 1).
        statistical_significance_level: p-value for layer 2.
        min_data_points: Min data points for statistical test.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    quality_drop_threshold: float = Field(default=0.10, ge=0.0, le=1.0)
    cost_increase_threshold: float = Field(default=0.20, ge=0.0, le=1.0)
    error_rate_increase_threshold: float = Field(default=0.15, ge=0.0, le=1.0)
    success_rate_drop_threshold: float = Field(default=0.10, ge=0.0, le=1.0)
    statistical_significance_level: float = Field(default=0.05, ge=0.001, le=0.5)
    min_data_points: int = Field(default=10, ge=2)


class GuardChainConfig(BaseModel):
    """Configuration for the proposal guard chain.

    Attributes:
        proposal_rate_limit: Max proposals per rate window.
        rate_limit_window_hours: Duration of the rate limit window.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    proposal_rate_limit: int = Field(default=10, ge=1)
    rate_limit_window_hours: int = Field(default=24, ge=1)


class ScheduleConfig(BaseModel):
    """Configuration for improvement cycle scheduling.

    Attributes:
        cycle_interval_hours: Hours between scheduled cycles.
        inflection_trigger_enabled: Trigger on performance inflections.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    cycle_interval_hours: int = Field(default=168, ge=1)
    inflection_trigger_enabled: bool = True


class PromptTuningConfig(BaseModel):
    """Configuration for prompt tuning strategy behavior.

    Attributes:
        default_evolution_mode: Default interaction mode with
            the per-agent evolution system.
        allowed_modes: Which evolution modes are available.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    default_evolution_mode: EvolutionMode = EvolutionMode.ORG_WIDE
    allowed_modes: tuple[Literal["org_wide", "override", "advisory"], ...] = (
        "org_wide",
        "override",
        "advisory",
    )


class SelfImprovementConfig(BaseModel):
    """Top-level configuration for the self-improving company meta-loop.

    Safe defaults:
    - Feature: disabled (opt-in)
    - Chief of Staff agent: disabled (opt-in)
    - Altitudes: config_tuning ON when enabled; architecture + prompt OFF
    - Guards: all enabled, approval gate mandatory
    - Rollout: before/after default, 48h observation window
    - Regression: tiered (threshold + statistical)
    - Schedule: weekly + inflection triggers

    Attributes:
        enabled: Master switch for the self-improvement system.
        chief_of_staff_enabled: Whether to enable the Chief of Staff
            agent persona.
        config_tuning_enabled: Enable config tuning proposals.
        architecture_proposals_enabled: Enable architecture proposals.
        prompt_tuning_enabled: Enable prompt tuning proposals.
        schedule: Cycle scheduling configuration.
        rollout: Rollout behavior configuration.
        regression: Regression detection thresholds.
        guards: Guard chain configuration.
        rules: Rule engine configuration.
        prompt_tuning: Prompt tuning strategy configuration.
        analysis_model: LLM model identifier for proposal analysis.
        analysis_temperature: Sampling temperature for analysis.
        analysis_max_tokens: Token budget for analysis responses.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    enabled: bool = False
    chief_of_staff_enabled: bool = False

    config_tuning_enabled: bool = True
    architecture_proposals_enabled: bool = False
    prompt_tuning_enabled: bool = False

    schedule: ScheduleConfig = Field(default_factory=ScheduleConfig)
    rollout: RolloutConfig = Field(default_factory=RolloutConfig)
    regression: RegressionConfig = Field(default_factory=RegressionConfig)
    guards: GuardChainConfig = Field(default_factory=GuardChainConfig)
    rules: RuleConfig = Field(default_factory=RuleConfig)
    prompt_tuning: PromptTuningConfig = Field(
        default_factory=PromptTuningConfig,
    )

    analysis_model: NotBlankStr = Field(
        default=NotBlankStr("example-small-001"),
        description="Model for proposal analysis LLM calls",
    )
    analysis_temperature: float = Field(default=0.3, ge=0.0, le=2.0)
    analysis_max_tokens: int = Field(default=4000, ge=100)
