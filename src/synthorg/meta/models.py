"""Domain models for the self-improving company meta-loop.

Defines improvement proposals, rollback plans, signal snapshots,
rule matches, guard results, and rollout outcomes that flow through
the meta-improvement pipeline.
"""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Self
from uuid import UUID, uuid4

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
    model_validator,
)

from synthorg.core.types import NotBlankStr  # noqa: TC001

# ── Enums ──────────────────────────────────────────────────────────


class ProposalAltitude(StrEnum):
    """Altitude of change a proposal targets."""

    CONFIG_TUNING = "config_tuning"
    ARCHITECTURE = "architecture"
    PROMPT_TUNING = "prompt_tuning"


class ProposalStatus(StrEnum):
    """Lifecycle status of an improvement proposal."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    APPLYING = "applying"
    APPLIED = "applied"
    ROLLED_BACK = "rolled_back"
    REGRESSED = "regressed"


class RolloutStrategyType(StrEnum):
    """How an approved proposal is deployed."""

    BEFORE_AFTER = "before_after"
    CANARY = "canary"


class EvolutionMode(StrEnum):
    """How prompt tuning proposals interact with agent evolution."""

    ORG_WIDE = "org_wide"
    OVERRIDE = "override"
    ADVISORY = "advisory"


class RuleSeverity(StrEnum):
    """Severity of a rule match."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class GuardVerdict(StrEnum):
    """Outcome of a guard evaluation."""

    PASSED = "passed"
    REJECTED = "rejected"


class RolloutOutcome(StrEnum):
    """Final outcome of a rollout."""

    SUCCESS = "success"
    REGRESSED = "regressed"
    ROLLED_BACK = "rolled_back"
    FAILED = "failed"


class RegressionVerdict(StrEnum):
    """Result of a regression check."""

    NO_REGRESSION = "no_regression"
    THRESHOLD_BREACH = "threshold_breach"
    STATISTICAL_REGRESSION = "statistical_regression"
    INSUFFICIENT_DATA = "insufficient_data"


# ── Rollback models ────────────────────────────────────────────────


class RollbackOperation(BaseModel):
    """A single inverse operation in a rollback plan.

    Attributes:
        operation_type: Kind of reversal (revert_config, delete_role, etc.).
        target: What to revert (config path, role name, etc.).
        previous_value: Value to restore (None for deletions).
        description: Human-readable description.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    operation_type: NotBlankStr
    target: NotBlankStr
    previous_value: Any = None
    description: NotBlankStr


class RollbackPlan(BaseModel):
    """Concrete plan for reverting an improvement proposal.

    Attributes:
        operations: Ordered inverse operations.
        dependencies: Proposal IDs that must rollback first.
        validation_check: Post-rollback assertion description.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    operations: tuple[RollbackOperation, ...] = Field(min_length=1)
    dependencies: tuple[UUID, ...] = ()
    validation_check: NotBlankStr


# ── Change models (altitude-specific) ─────────────────────────────


class ConfigChange(BaseModel):
    """A single config field change.

    Attributes:
        path: JSON-path to the config field (e.g. ``budget.monthly_usd``).
        old_value: Current value.
        new_value: Proposed value.
        description: Why this change is proposed.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    path: NotBlankStr
    old_value: Any = None
    new_value: Any = None
    description: NotBlankStr


class ArchitectureChange(BaseModel):
    """A structural change to the organization.

    Attributes:
        operation: Type of change (create_role, create_department,
            modify_workflow, remove_role, etc.).
        target_name: Name of the entity being changed.
        payload: Structured change data (operation-specific).
        description: Why this change is proposed.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    operation: NotBlankStr
    target_name: NotBlankStr
    payload: dict[str, Any] = Field(default_factory=dict)
    description: NotBlankStr


class PromptChange(BaseModel):
    """An org-wide prompt policy change.

    Attributes:
        principle_text: The constitutional principle to inject.
        target_scope: Who this applies to (role name, department, or ``all``).
        evolution_mode: How this interacts with per-agent evolution.
        description: Why this change is proposed.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    principle_text: NotBlankStr
    target_scope: NotBlankStr
    evolution_mode: EvolutionMode = EvolutionMode.ORG_WIDE
    description: NotBlankStr


# ── Proposal rationale ─────────────────────────────────────────────


class ProposalRationale(BaseModel):
    """Evidence and reasoning behind an improvement proposal.

    Attributes:
        signal_summary: Key signals that motivated this proposal.
        pattern_detected: The pattern or issue identified.
        expected_impact: What improvement is expected.
        confidence_reasoning: Why the confidence level was assigned.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    signal_summary: NotBlankStr
    pattern_detected: NotBlankStr
    expected_impact: NotBlankStr
    confidence_reasoning: NotBlankStr


# ── Improvement proposal ──────────────────────────────────────────


class ImprovementProposal(BaseModel):
    """A proposed improvement to the company deployment.

    Generated by an ``ImprovementStrategy``, validated by
    ``ProposalGuard``(s), and applied via a ``ProposalApplier``
    after mandatory human approval.

    Attributes:
        id: Unique proposal identifier.
        altitude: Which altitude of change this targets.
        title: Short human-readable title.
        description: Detailed description of the proposed change.
        rationale: Evidence and reasoning.
        config_changes: Config field changes (config_tuning altitude).
        architecture_changes: Structural changes (architecture altitude).
        prompt_changes: Prompt policy changes (prompt_tuning altitude).
        rollback_plan: Concrete rollback plan.
        rollout_strategy: How to deploy the change.
        confidence: Strategy's confidence in this proposal (0-1).
        source_rule: Name of the rule that triggered this proposal.
        status: Lifecycle status.
        proposed_at: When the proposal was generated.
        decided_at: When the proposal was approved/rejected.
        decided_by: Who approved/rejected the proposal.
        decision_reason: Reason for approval/rejection.
        observation_window_hours: Post-apply observation window.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    id: UUID = Field(default_factory=uuid4)
    altitude: ProposalAltitude
    title: NotBlankStr
    description: NotBlankStr
    rationale: ProposalRationale
    config_changes: tuple[ConfigChange, ...] = ()
    architecture_changes: tuple[ArchitectureChange, ...] = ()
    prompt_changes: tuple[PromptChange, ...] = ()
    rollback_plan: RollbackPlan
    rollout_strategy: RolloutStrategyType = RolloutStrategyType.BEFORE_AFTER
    confidence: float = Field(ge=0.0, le=1.0)
    source_rule: NotBlankStr | None = None
    status: ProposalStatus = ProposalStatus.PENDING
    proposed_at: AwareDatetime = Field(
        default_factory=lambda: datetime.now(UTC),
    )
    decided_at: AwareDatetime | None = None
    decided_by: NotBlankStr | None = None
    decision_reason: NotBlankStr | None = None
    observation_window_hours: int = Field(default=48, ge=1)

    @model_validator(mode="after")
    def _validate_decision_consistency(self) -> Self:
        """Ensure decided_at/decided_by/decision_reason are all-or-nothing."""
        decided = (self.decided_at, self.decided_by, self.decision_reason)
        if any(decided) and not all(decided):
            msg = (
                "decided_at, decided_by, and decision_reason "
                "must all be set or all be None"
            )
            raise ValueError(msg)
        terminal = {
            ProposalStatus.APPROVED,
            ProposalStatus.REJECTED,
            ProposalStatus.APPLIED,
        }
        if self.status in terminal and not all(decided):
            msg = "non-pending proposals must include decision metadata"
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _validate_changes_match_altitude(self) -> Self:
        """Ensure only the declared altitude carries changes."""
        if self.altitude == ProposalAltitude.CONFIG_TUNING and (
            not self.config_changes or self.architecture_changes or self.prompt_changes
        ):
            msg = "config_tuning proposals must contain only config_changes"
            raise ValueError(msg)
        if self.altitude == ProposalAltitude.ARCHITECTURE and (
            not self.architecture_changes or self.config_changes or self.prompt_changes
        ):
            msg = "architecture proposals must contain only architecture_changes"
            raise ValueError(msg)
        if self.altitude == ProposalAltitude.PROMPT_TUNING and (
            not self.prompt_changes or self.config_changes or self.architecture_changes
        ):
            msg = "prompt_tuning proposals must contain only prompt_changes"
            raise ValueError(msg)
        return self

    @computed_field  # type: ignore[prop-decorator]
    @property
    def change_count(self) -> int:
        """Total number of changes across all altitudes."""
        return (
            len(self.config_changes)
            + len(self.architecture_changes)
            + len(self.prompt_changes)
        )


# ── Rule match ─────────────────────────────────────────────────────


class RuleMatch(BaseModel):
    """Result of a signal rule detecting a pattern.

    Attributes:
        rule_name: Name of the rule that fired.
        severity: How urgent this match is.
        description: Human-readable explanation.
        signal_context: Specific data that triggered the rule.
        suggested_altitudes: Which strategies should generate proposals.
        matched_at: When the match was detected.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    rule_name: NotBlankStr
    severity: RuleSeverity
    description: NotBlankStr
    signal_context: dict[str, Any] = Field(default_factory=dict)
    suggested_altitudes: tuple[ProposalAltitude, ...] = Field(min_length=1)
    matched_at: AwareDatetime = Field(
        default_factory=lambda: datetime.now(UTC),
    )


# ── Guard result ───────────────────────────────────────────────────


class GuardResult(BaseModel):
    """Outcome of a guard evaluating a proposal.

    Attributes:
        guard_name: Name of the guard.
        verdict: Whether the proposal passed or was rejected.
        reason: Explanation (required on rejection).
        evaluated_at: When the evaluation happened.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    guard_name: NotBlankStr
    verdict: GuardVerdict
    reason: NotBlankStr | None = None
    evaluated_at: AwareDatetime = Field(
        default_factory=lambda: datetime.now(UTC),
    )

    @model_validator(mode="after")
    def _validate_rejection_has_reason(self) -> Self:
        """Rejected verdicts must include a reason."""
        if self.verdict == GuardVerdict.REJECTED and not self.reason:
            msg = "rejected guard verdicts must include a reason"
            raise ValueError(msg)
        return self


# ── Rollout result ─────────────────────────────────────────────────


class RolloutResult(BaseModel):
    """Outcome of a staged rollout.

    Attributes:
        proposal_id: Which proposal was rolled out.
        outcome: Final result.
        regression_verdict: Regression detection result (if checked).
        observation_hours_elapsed: How long the observation ran.
        details: Additional context about the rollout.
        completed_at: When the rollout finished.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    proposal_id: UUID
    outcome: RolloutOutcome
    regression_verdict: RegressionVerdict | None = None
    observation_hours_elapsed: float = Field(ge=0.0)
    details: NotBlankStr | None = None
    completed_at: AwareDatetime = Field(
        default_factory=lambda: datetime.now(UTC),
    )

    @model_validator(mode="after")
    def _validate_regressed_has_verdict(self) -> Self:
        """Regressed outcomes must include a regression verdict."""
        if self.outcome == RolloutOutcome.REGRESSED and not self.regression_verdict:
            msg = "regressed outcomes must include regression_verdict"
            raise ValueError(msg)
        return self


# ── Apply result ───────────────────────────────────────────────────


class ApplyResult(BaseModel):
    """Outcome of applying a proposal change.

    Attributes:
        success: Whether the apply succeeded.
        error_message: Error description on failure.
        changes_applied: Number of individual changes applied.
        applied_at: When the apply completed.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    success: bool
    error_message: NotBlankStr | None = None
    changes_applied: int = Field(ge=0)
    applied_at: AwareDatetime = Field(
        default_factory=lambda: datetime.now(UTC),
    )

    @model_validator(mode="after")
    def _validate_failure_has_message(self) -> Self:
        """Failed applies must include an error message."""
        if not self.success and not self.error_message:
            msg = "failed apply results must include an error_message"
            raise ValueError(msg)
        return self


# ── Regression thresholds ──────────────────────────────────────────


class RegressionThresholds(BaseModel):
    """Configurable thresholds for regression detection.

    All values are fractional (0.10 = 10% degradation).

    Attributes:
        quality_drop: Max acceptable quality score drop.
        cost_increase: Max acceptable cost increase.
        error_rate_increase: Max acceptable error rate increase.
        success_rate_drop: Max acceptable success rate drop.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    quality_drop: float = Field(default=0.10, ge=0.0, le=1.0)
    cost_increase: float = Field(default=0.20, ge=0.0, le=1.0)
    error_rate_increase: float = Field(default=0.15, ge=0.0, le=1.0)
    success_rate_drop: float = Field(default=0.10, ge=0.0, le=1.0)


# ── Regression result ──────────────────────────────────────────────


class RegressionResult(BaseModel):
    """Outcome of a regression detection check.

    Attributes:
        verdict: Whether regression was detected.
        breached_metric: Which metric breached (if any).
        baseline_value: Metric value before the change.
        current_value: Metric value after the change.
        threshold: Threshold that was breached.
        p_value: Statistical p-value (for statistical checks).
        checked_at: When the check was performed.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    verdict: RegressionVerdict
    breached_metric: NotBlankStr | None = None
    baseline_value: float | None = None
    current_value: float | None = None
    threshold: float | None = None
    p_value: float | None = None
    checked_at: AwareDatetime = Field(
        default_factory=lambda: datetime.now(UTC),
    )

    @model_validator(mode="after")
    def _validate_breach_has_details(self) -> Self:
        """Threshold breaches must include metric details."""
        if self.verdict == RegressionVerdict.THRESHOLD_BREACH:
            if not self.breached_metric:
                msg = "threshold breaches must identify the breached metric"
                raise ValueError(msg)
            if self.baseline_value is None or self.current_value is None:
                msg = "threshold breaches must include baseline and current values"
                raise ValueError(msg)
        if (
            self.verdict == RegressionVerdict.STATISTICAL_REGRESSION
            and self.p_value is None
        ):
            msg = "statistical regressions must include p_value"
            raise ValueError(msg)
        return self


# ── Signal summary models ──────────────────────────────────────────


class TrendDirection(StrEnum):
    """Direction of a metric trend."""

    IMPROVING = "improving"
    DECLINING = "declining"
    STABLE = "stable"


class MetricSummary(BaseModel):
    """Summary of a single metric across the org.

    Attributes:
        name: Metric name.
        value: Current aggregate value.
        trend: Direction over the observation window.
        window_days: How many days the trend covers.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    name: NotBlankStr
    value: float
    trend: TrendDirection = TrendDirection.STABLE
    window_days: int = Field(default=7, ge=1)


class OrgPerformanceSummary(BaseModel):
    """Org-wide performance signal summary.

    Attributes:
        avg_quality_score: Org average quality (0-10).
        avg_success_rate: Org average success rate (0-1).
        avg_collaboration_score: Org average collaboration (0-10).
        metrics: Per-metric summaries with trends.
        agent_count: Number of active agents.
        department_summaries: Per-department metric rollups.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    avg_quality_score: float = Field(ge=0.0, le=10.0)
    avg_success_rate: float = Field(ge=0.0, le=1.0)
    avg_collaboration_score: float = Field(ge=0.0, le=10.0)
    metrics: tuple[MetricSummary, ...] = ()
    agent_count: int = Field(ge=0)
    department_summaries: dict[str, dict[str, float]] = Field(
        default_factory=dict,
    )


class OrgBudgetSummary(BaseModel):
    """Org-wide budget signal summary.

    Attributes:
        total_spend_usd: Total spend in current period.
        productive_ratio: Fraction of spend on productive work.
        coordination_ratio: Fraction of spend on coordination.
        system_ratio: Fraction of spend on system overhead.
        days_until_exhausted: Forecast days until budget runs out.
        forecast_confidence: Confidence in the forecast (0-1).
        orchestration_overhead: Coordination/productive token ratio.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    total_spend_usd: float = Field(ge=0.0)
    productive_ratio: float = Field(ge=0.0, le=1.0)
    coordination_ratio: float = Field(ge=0.0, le=1.0)
    system_ratio: float = Field(ge=0.0, le=1.0)
    days_until_exhausted: int | None = None
    forecast_confidence: float = Field(ge=0.0, le=1.0)
    orchestration_overhead: float = Field(ge=0.0)


class OrgCoordinationSummary(BaseModel):
    """Org-wide coordination metrics summary.

    Attributes:
        coordination_efficiency: Success-rate-adjusted turn efficiency.
        coordination_overhead_pct: Percentage overhead for MAS vs SAS.
        error_amplification: MAS/SAS error rate ratio.
        message_density: Messages per reasoning turn.
        redundancy_rate: Mean output similarity (0-1).
        straggler_gap_ratio: Slowest/mean completion ratio.
        sample_count: Number of tasks used for these metrics.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    coordination_efficiency: float | None = None
    coordination_overhead_pct: float | None = None
    error_amplification: float | None = None
    message_density: float | None = None
    redundancy_rate: float | None = None
    straggler_gap_ratio: float | None = None
    sample_count: int = Field(default=0, ge=0)


class ScalingDecisionSummary(BaseModel):
    """Summary of a recent scaling decision and its outcome.

    Attributes:
        action_type: What was proposed (hire/prune/hold).
        outcome: What happened (executed/failed/deferred/rejected).
        source_strategy: Which strategy proposed it.
        rationale: Why.
        created_at: When the decision was made.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    action_type: NotBlankStr
    outcome: NotBlankStr
    source_strategy: NotBlankStr
    rationale: NotBlankStr
    created_at: AwareDatetime


class OrgScalingSummary(BaseModel):
    """Org-wide scaling signal summary.

    Attributes:
        recent_decisions: Recent scaling decisions with outcomes.
        total_decisions: Total decisions in the window.
        success_rate: Fraction of decisions that were executed.
        most_common_signal: Most frequently triggered signal.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    recent_decisions: tuple[ScalingDecisionSummary, ...] = ()
    total_decisions: int = Field(default=0, ge=0)
    success_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    most_common_signal: NotBlankStr | None = None


class ErrorCategorySummary(BaseModel):
    """Summary of errors in a single category.

    Attributes:
        category: Error category name.
        count: Number of findings in this category.
        avg_severity: Average severity (low=1, medium=2, high=3).
        trend: Whether this category is increasing or decreasing.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    category: NotBlankStr
    count: int = Field(ge=0)
    avg_severity: float = Field(ge=1.0, le=3.0)
    trend: TrendDirection = TrendDirection.STABLE


class OrgErrorSummary(BaseModel):
    """Org-wide error taxonomy signal summary.

    Attributes:
        total_findings: Total error findings in the window.
        categories: Per-category summaries.
        most_severe_category: Category with highest avg severity.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    total_findings: int = Field(default=0, ge=0)
    categories: tuple[ErrorCategorySummary, ...] = ()
    most_severe_category: NotBlankStr | None = None

    @model_validator(mode="after")
    def _validate_severe_category_exists(self) -> Self:
        """Ensure most_severe_category references an actual category."""
        if self.most_severe_category:
            names = {c.category for c in self.categories}
            if self.most_severe_category not in names:
                msg = (
                    f"most_severe_category '{self.most_severe_category}' "
                    f"not found in categories"
                )
                raise ValueError(msg)
        return self


class EvolutionOutcomeSummary(BaseModel):
    """Summary of a recent evolution outcome.

    Attributes:
        agent_id: Which agent was evolved.
        axis: Which axis was adapted.
        applied: Whether the adaptation was applied.
        proposed_at: When the proposal was generated.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    agent_id: NotBlankStr
    axis: NotBlankStr
    applied: bool
    proposed_at: AwareDatetime


class OrgEvolutionSummary(BaseModel):
    """Org-wide evolution signal summary.

    Attributes:
        recent_outcomes: Recent evolution outcomes.
        total_proposals: Total proposals in the window.
        approval_rate: Fraction of proposals approved/applied.
        most_adapted_axis: Most frequently adapted axis.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    recent_outcomes: tuple[EvolutionOutcomeSummary, ...] = ()
    total_proposals: int = Field(default=0, ge=0)
    approval_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    most_adapted_axis: NotBlankStr | None = None


class OrgTelemetrySummary(BaseModel):
    """Org-wide telemetry signal summary.

    Attributes:
        event_count: Total telemetry events in the window.
        top_event_types: Most frequent event type names.
        error_event_count: Number of error-level events.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    event_count: int = Field(default=0, ge=0)
    top_event_types: tuple[str, ...] = ()
    error_event_count: int = Field(default=0, ge=0)


# ── Composite signal snapshot ──────────────────────────────────────


class OrgSignalSnapshot(BaseModel):
    """Composite snapshot of all org-wide signals.

    Assembled by the snapshot builder from all signal aggregators.
    Passed to the rule engine and improvement strategies.

    Attributes:
        performance: Performance signal summary.
        budget: Budget signal summary.
        coordination: Coordination metrics summary.
        scaling: Scaling signal summary.
        errors: Error taxonomy summary.
        evolution: Evolution signal summary.
        telemetry: Telemetry signal summary.
        collected_at: When the snapshot was assembled.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    performance: OrgPerformanceSummary
    budget: OrgBudgetSummary
    coordination: OrgCoordinationSummary
    scaling: OrgScalingSummary
    errors: OrgErrorSummary
    evolution: OrgEvolutionSummary
    telemetry: OrgTelemetrySummary
    collected_at: AwareDatetime = Field(
        default_factory=lambda: datetime.now(UTC),
    )
