"""Configuration for the agent evolution system.

Defines frozen Pydantic config models for each pluggable axis
(triggers, proposers, adapters, guards, memory, identity store)
with safe defaults matching the issue specification.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from synthorg.core.types import NotBlankStr  # noqa: TC001
from synthorg.engine.identity.store.config import (
    IdentityStoreConfig,
)
from synthorg.memory.procedural.capture.config import (
    CaptureConfig,
)
from synthorg.memory.procedural.propagation.config import (
    PropagationConfig,
)
from synthorg.memory.procedural.pruning.config import (
    PruningConfig,
)


class TriggerConfig(BaseModel):
    """Configuration for evolution triggers.

    Attributes:
        types: Which trigger types to enable.
        batched_interval_seconds: Interval for batched trigger.
        per_task_min_tasks: Min tasks between per-task triggers.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    types: tuple[Literal["batched", "inflection", "per_task"], ...] = (
        "batched",
        "inflection",
    )
    batched_interval_seconds: int = Field(
        default=86400, ge=1, description="Seconds between batched runs"
    )
    per_task_min_tasks: int = Field(
        default=1,
        ge=1,
        description="Min tasks between per-task triggers",
    )


class ProposerConfig(BaseModel):
    """Configuration for evolution proposers.

    Attributes:
        type: Proposer strategy to use.
        model: LLM model identifier for analysis.
        temperature: Sampling temperature.
        max_tokens: Token budget for proposer response.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    type: Literal["separate_analyzer", "self_report", "composite"] = "composite"
    model: NotBlankStr = Field(
        default="example-small-001",
        description="Model for proposer LLM calls",
    )
    temperature: float = Field(default=0.3, ge=0.0, le=2.0)
    max_tokens: int = Field(default=2000, ge=100)


class AdapterConfig(BaseModel):
    """Configuration for which adaptation axes are enabled.

    Attributes:
        identity: Enable identity mutations (highest risk).
        strategy_selection: Enable strategy preference changes.
        prompt_template: Enable prompt injection of learned memories.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    identity: bool = False
    strategy_selection: bool = True
    prompt_template: bool = True


class GuardConfig(BaseModel):
    """Configuration for evolution guards.

    Attributes:
        review_gate: Enable human review for risky adaptations.
        rollback: Enable regression-triggered rollback.
        rollback_window_tasks: Tasks to monitor post-adaptation.
        rollback_regression_threshold: Quality drop triggering rollback.
        rate_limit: Enable per-agent rate limiting.
        rate_limit_per_day: Max adaptations per agent per day.
        shadow_evaluation: Enable shadow evaluation (opt-in, stub).
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    review_gate: bool = True
    rollback: bool = True
    rollback_window_tasks: int = Field(default=20, ge=1)
    rollback_regression_threshold: float = Field(default=0.1, ge=0.0, le=1.0)
    rate_limit: bool = True
    rate_limit_per_day: int = Field(default=3, ge=1)
    shadow_evaluation: bool = False


class MemoryEvolutionConfig(BaseModel):
    """Configuration for memory-related evolution extensions.

    Attributes:
        capture: Procedural memory capture strategy config.
        pruning: Procedural memory pruning strategy config.
        propagation: Cross-agent propagation strategy config.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    capture: CaptureConfig = Field(default_factory=CaptureConfig)
    pruning: PruningConfig = Field(default_factory=PruningConfig)
    propagation: PropagationConfig = Field(
        default_factory=PropagationConfig,
    )


class EvolutionConfig(BaseModel):
    """Top-level configuration for the agent evolution system.

    Safe defaults:
    - Triggers: batched (daily) + inflection
    - Proposer: composite (analyzer for failures, self-report for success)
    - Adapters: prompt_template ON, strategy_selection ON, identity OFF
    - Guards: review_gate + rollback + rate_limit ON; shadow OFF
    - Identity store: append_only
    - Propagation: none (opt-in per org)

    Attributes:
        enabled: Master switch for the evolution system.
        triggers: Trigger strategy configuration.
        proposer: Proposer strategy configuration.
        adapters: Which adaptation axes are enabled.
        guards: Guard configuration.
        memory: Memory extension configuration.
        identity_store: Identity version store configuration.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    enabled: bool = True
    triggers: TriggerConfig = Field(default_factory=TriggerConfig)
    proposer: ProposerConfig = Field(default_factory=ProposerConfig)
    adapters: AdapterConfig = Field(default_factory=AdapterConfig)
    guards: GuardConfig = Field(default_factory=GuardConfig)
    memory: MemoryEvolutionConfig = Field(
        default_factory=MemoryEvolutionConfig,
    )
    identity_store: IdentityStoreConfig = Field(
        default_factory=IdentityStoreConfig,
    )
