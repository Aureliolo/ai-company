"""Data models for the A/B test rollout strategy.

Defines group assignment, per-group metrics, and comparison
result models used by ``ABTestRollout`` and ``ABTestComparator``.
"""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Self
from uuid import UUID  # noqa: TC003 -- Pydantic needs at runtime

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from synthorg.core.types import NotBlankStr  # noqa: TC001 -- Pydantic needs at runtime


class ABTestGroup(StrEnum):
    """Which group an agent belongs to in an A/B test."""

    CONTROL = "control"
    TREATMENT = "treatment"


class ABTestVerdict(StrEnum):
    """Outcome of comparing control vs treatment groups."""

    TREATMENT_WINS = "treatment_wins"
    CONTROL_WINS = "control_wins"
    INCONCLUSIVE = "inconclusive"
    TREATMENT_REGRESSED = "treatment_regressed"


class GroupAssignment(BaseModel):
    """Deterministic assignment of agents to control/treatment groups.

    Attributes:
        proposal_id: Which proposal this assignment belongs to.
        control_agent_ids: Agent IDs in the control group.
        treatment_agent_ids: Agent IDs in the treatment group.
        control_fraction: Fraction used for the control group.
        assigned_at: When the assignment was computed.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    proposal_id: UUID
    control_agent_ids: tuple[NotBlankStr, ...] = ()
    treatment_agent_ids: tuple[NotBlankStr, ...] = ()
    control_fraction: float = Field(gt=0.0, lt=1.0)
    assigned_at: AwareDatetime = Field(
        default_factory=lambda: datetime.now(UTC),
    )

    @model_validator(mode="after")
    def _validate_disjoint_groups(self) -> Self:
        """Control and treatment groups must not overlap."""
        overlap = set(self.control_agent_ids) & set(
            self.treatment_agent_ids,
        )
        if overlap:
            msg = "control and treatment groups must be disjoint"
            raise ValueError(msg)
        return self


class GroupMetrics(BaseModel):
    """Aggregated metrics for a single A/B test group.

    Attributes:
        group: Which group (control or treatment).
        agent_count: Number of agents in this group.
        observation_count: Number of metric samples collected.
        avg_quality_score: Average quality score (0-10).
        avg_success_rate: Average task success rate (0-1).
        total_spend_usd: Total spend for this group.
        collected_at: When these metrics were collected.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    group: ABTestGroup
    agent_count: int = Field(ge=0)
    observation_count: int = Field(ge=0)
    avg_quality_score: float = Field(ge=0.0, le=10.0)
    avg_success_rate: float = Field(ge=0.0, le=1.0)
    total_spend_usd: float = Field(ge=0.0)
    collected_at: AwareDatetime = Field(
        default_factory=lambda: datetime.now(UTC),
    )


class ABTestComparison(BaseModel):
    """Result of comparing control vs treatment group metrics.

    Attributes:
        verdict: Outcome of the comparison.
        control_metrics: Metrics from the control group.
        treatment_metrics: Metrics from the treatment group.
        effect_size: Cohen's d estimate (None if insufficient data).
        p_value: Statistical significance (None if insufficient data).
        regressed_metrics: Names of metrics where treatment was worse.
        compared_at: When the comparison was performed.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    verdict: ABTestVerdict
    control_metrics: GroupMetrics
    treatment_metrics: GroupMetrics
    effect_size: float | None = None
    p_value: float | None = None
    regressed_metrics: tuple[NotBlankStr, ...] = ()
    compared_at: AwareDatetime = Field(
        default_factory=lambda: datetime.now(UTC),
    )

    @model_validator(mode="after")
    def _validate_regression_has_metrics(self) -> Self:
        """Treatment regressions must identify which metrics regressed."""
        if (
            self.verdict == ABTestVerdict.TREATMENT_REGRESSED
            and not self.regressed_metrics
        ):
            msg = "treatment regressions must identify regressed_metrics"
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _validate_winner_has_stats(self) -> Self:
        """Treatment wins must include effect_size and p_value."""
        if self.verdict == ABTestVerdict.TREATMENT_WINS and (
            self.effect_size is None or self.p_value is None
        ):
            msg = "treatment wins must include effect_size and p_value"
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _validate_statistic_bounds(self) -> Self:
        """Statistical fields must be in valid ranges."""
        if self.p_value is not None and not 0.0 <= self.p_value <= 1.0:
            msg = "p_value must be in [0.0, 1.0]"
            raise ValueError(msg)
        if self.effect_size is not None and self.effect_size < 0.0:
            msg = "effect_size must be non-negative"
            raise ValueError(msg)
        return self
