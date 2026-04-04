"""Crash recovery strategy protocol and fail-and-reassign implementation.

Defines the ``RecoveryStrategy`` protocol and the default
``FailAndReassignStrategy`` that transitions a crashed task execution
from its current status (typically ``IN_PROGRESS``) to ``FAILED``
status, captures a redacted context snapshot, and reports whether the
task can be reassigned (based on retry count vs max retries).

See the Crash Recovery section of the Engine design page.
"""

import json
from typing import Any, Final, Protocol, Self, runtime_checkable

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
    field_validator,
    model_validator,
)

from synthorg.core.enums import FailureCategory, TaskStatus
from synthorg.core.types import NotBlankStr  # noqa: TC001
from synthorg.engine.context import AgentContext, AgentContextSnapshot  # noqa: TC001
from synthorg.engine.immutable import deep_copy_mapping
from synthorg.engine.stagnation.models import StagnationResult  # noqa: TC001
from synthorg.engine.task_execution import TaskExecution  # noqa: TC001
from synthorg.observability import get_logger
from synthorg.observability.events.execution import (
    EXECUTION_RECOVERY_COMPLETE,
    EXECUTION_RECOVERY_DIAGNOSIS,
    EXECUTION_RECOVERY_SNAPSHOT,
    EXECUTION_RECOVERY_START,
)

logger = get_logger(__name__)


# Keyword rules for inferring failure category from error messages.
# Evaluated in order; first match wins.
_FAILURE_CATEGORY_RULES: tuple[tuple[tuple[str, ...], FailureCategory], ...] = (
    (("budget",), FailureCategory.BUDGET_EXCEEDED),
    (("timeout", "timed out"), FailureCategory.TIMEOUT),
    (("stagnation",), FailureCategory.STAGNATION),
    (("delegation",), FailureCategory.DELEGATION_FAILED),
    (("quality", "criteria"), FailureCategory.QUALITY_GATE_FAILED),
)


def infer_failure_category(error_message: str) -> FailureCategory:
    """Infer a failure category from an error message via keyword matching.

    Simple heuristic for v1 -- matches keywords case-insensitively in
    the declared rule order (first match wins).  Returns
    ``FailureCategory.UNKNOWN`` when nothing matches: honest failure
    classification is better than silently defaulting to
    ``TOOL_FAILURE``, which would masquerade unknown causes as tool
    failures in dashboards, reports, and reconciliation prompts.

    Future versions may derive categories from typed exceptions
    (e.g. ``BudgetExhaustedError`` -> ``BUDGET_EXCEEDED``) or from
    provider-specific error codes instead of string sniffing.

    Args:
        error_message: The error message to classify.

    Returns:
        The inferred ``FailureCategory`` or ``UNKNOWN`` when no rule
        matches.
    """
    lower = error_message.lower()
    for keywords, category in _FAILURE_CATEGORY_RULES:
        if any(kw in lower for kw in keywords):
            return category
    return FailureCategory.UNKNOWN


class RecoveryResult(BaseModel):
    """Frozen result of a recovery strategy invocation.

    Attributes:
        task_execution: Execution state after recovery (``FAILED`` for
            fail-and-reassign, original state for checkpoint resume).
        strategy_type: Identifier of the strategy used (e.g. ``"fail_reassign"``).
        can_reassign: Computed -- ``True`` when retry_count < task.max_retries.
            The caller (task router) is responsible for incrementing
            ``retry_count`` when creating the next ``TaskExecution``.
        context_snapshot: Redacted snapshot (no message contents).
        error_message: The error that triggered recovery.
        failure_category: Machine-readable failure classification.
        failure_context: Structured metadata for the failure (strategy-specific).
        criteria_failed: Acceptance criteria that were not met.
        stagnation_evidence: Stagnation detection result when failure
            involves stagnation.
        checkpoint_context_json: Serialized ``AgentContext`` for resume
            (set by ``CheckpointRecoveryStrategy``, ``None`` otherwise).
        resume_attempt: Current resume attempt number (0 when not resuming).
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    task_execution: TaskExecution = Field(
        description="Execution state after recovery",
    )
    strategy_type: NotBlankStr = Field(
        description="Identifier of the recovery strategy used",
    )
    context_snapshot: AgentContextSnapshot = Field(
        description="Redacted context snapshot (no message contents)",
    )
    error_message: NotBlankStr = Field(
        description="The error that triggered recovery",
    )
    failure_category: FailureCategory = Field(
        description="Machine-readable failure classification",
    )
    failure_context: dict[str, Any] = Field(
        description="Structured metadata for the failure",
    )
    criteria_failed: tuple[NotBlankStr, ...] = Field(
        default=(),
        description="Acceptance criteria that were not met",
    )
    stagnation_evidence: StagnationResult | None = Field(
        default=None,
        description="Stagnation detection result when applicable",
    )
    checkpoint_context_json: str | None = Field(
        default=None,
        description="Serialized AgentContext from checkpoint for resume",
    )
    resume_attempt: int = Field(
        default=0,
        ge=0,
        description="Current resume attempt number",
    )

    @field_validator("failure_context", mode="before")
    @classmethod
    def _deep_copy_failure_context(cls, value: object) -> object:
        """Deep-copy failure_context at construction boundary."""
        return deep_copy_mapping(value)

    @model_validator(mode="after")
    def _validate_checkpoint_consistency(self) -> Self:
        """Validate checkpoint_context_json and resume_attempt are consistent."""
        has_json = self.checkpoint_context_json is not None
        has_attempt = self.resume_attempt > 0
        if has_json != has_attempt:
            msg = (
                "checkpoint_context_json and resume_attempt must be "
                "consistent: both set or both at default"
            )
            raise ValueError(msg)
        if self.checkpoint_context_json is not None:
            try:
                parsed = json.loads(self.checkpoint_context_json)
            except json.JSONDecodeError as exc:
                msg = f"checkpoint_context_json must be valid JSON: {exc}"
                raise ValueError(msg) from exc
            if not isinstance(parsed, dict):
                msg = "checkpoint_context_json must be a JSON object"
                raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _validate_failure_category_invariants(self) -> Self:
        """Enforce cross-field invariants between failure_category and evidence.

        - ``stagnation_evidence`` is set iff ``failure_category`` is
          ``STAGNATION`` (carrying evidence alongside a mismatched
          category is a lie; a STAGNATION verdict without evidence is
          missing data).
        - ``criteria_failed`` must be non-empty when
          ``failure_category`` is ``QUALITY_GATE_FAILED`` (if we know
          the quality gate failed we must record which criterion).
        """
        if self.failure_category is FailureCategory.STAGNATION:
            if self.stagnation_evidence is None:
                msg = (
                    "stagnation_evidence is required when failure_category "
                    "is STAGNATION"
                )
                raise ValueError(msg)
        elif self.stagnation_evidence is not None:
            msg = (
                "stagnation_evidence must be None when failure_category is "
                f"{self.failure_category.value!r}"
            )
            raise ValueError(msg)

        if (
            self.failure_category is FailureCategory.QUALITY_GATE_FAILED
            and not self.criteria_failed
        ):
            msg = (
                "criteria_failed must be non-empty when failure_category "
                "is QUALITY_GATE_FAILED"
            )
            raise ValueError(msg)
        return self

    @computed_field(  # type: ignore[prop-decorator]
        description="Whether the task can be reassigned for retry",
    )
    @property
    def can_reassign(self) -> bool:
        """Whether the task can be reassigned for retry.

        Assumes the caller (task router) will increment ``retry_count``
        when creating the next ``TaskExecution`` for the reassigned task.
        """
        return self.task_execution.retry_count < self.task_execution.task.max_retries

    @computed_field(  # type: ignore[prop-decorator]
        description="Whether execution can resume from a checkpoint",
    )
    @property
    def can_resume(self) -> bool:
        """Whether execution can resume from a persisted checkpoint."""
        return self.checkpoint_context_json is not None


@runtime_checkable
class RecoveryStrategy(Protocol):
    """Protocol for crash recovery strategies.

    Implementations decide how to handle a failed task execution.
    Strategies may transition the task status, capture diagnostics,
    and report recovery options (e.g. reassignment, checkpoint resume).
    """

    async def recover(
        self,
        *,
        task_execution: TaskExecution,
        error_message: str,
        context: AgentContext,
    ) -> RecoveryResult:
        """Apply recovery to a failed task execution.

        Args:
            task_execution: Current execution state (typically
                ``IN_PROGRESS``, but may be ``ASSIGNED`` for early
                setup failures).
            error_message: Description of the failure.
            context: Full agent context at the time of failure.

        Returns:
            ``RecoveryResult`` with the updated execution and diagnostics.
        """
        ...

    async def finalize(
        self,
        execution_id: str,
    ) -> None:
        """Post-resume cleanup hook.

        Called after a successful resume (non-ERROR termination) to
        clean up strategy-specific state.  No-op by default.
        """
        ...

    def get_strategy_type(self) -> str:
        """Return the strategy type identifier."""
        ...


class FailAndReassignStrategy:
    """Default recovery: transition to FAILED and report reassignment eligibility.

    1. Capture a redacted ``AgentContextSnapshot`` (excludes message
       contents to prevent leaking sensitive prompts/tool outputs).
    2. Log the snapshot at ERROR level.
    3. Transition ``TaskExecution`` to ``FAILED`` with the error as reason.
    4. Report ``can_reassign = retry_count < task.max_retries``.
    """

    STRATEGY_TYPE: Final[str] = "fail_reassign"

    async def recover(
        self,
        *,
        task_execution: TaskExecution,
        error_message: str,
        context: AgentContext,
    ) -> RecoveryResult:
        """Apply fail-and-reassign recovery.

        Args:
            task_execution: Current execution state.
            error_message: Description of the failure.
            context: Full agent context at the time of failure.

        Returns:
            ``RecoveryResult`` with FAILED execution and reassignment info.
        """
        logger.info(
            EXECUTION_RECOVERY_START,
            task_id=task_execution.task.id,
            strategy=self.STRATEGY_TYPE,
            retry_count=task_execution.retry_count,
        )

        snapshot = context.to_snapshot()
        logger.error(
            EXECUTION_RECOVERY_SNAPSHOT,
            task_id=task_execution.task.id,
            turn_count=snapshot.turn_count,
            cost_usd=snapshot.accumulated_cost.cost_usd,
            error_message=error_message,
        )

        failed_execution = task_execution.with_transition(
            TaskStatus.FAILED,
            reason=error_message,
        )

        category = infer_failure_category(error_message)
        result = RecoveryResult(
            task_execution=failed_execution,
            strategy_type=self.STRATEGY_TYPE,
            context_snapshot=snapshot,
            error_message=error_message,
            failure_category=category,
            failure_context={
                "strategy_type": self.STRATEGY_TYPE,
            },
        )

        logger.info(
            EXECUTION_RECOVERY_DIAGNOSIS,
            task_id=task_execution.task.id,
            failure_category=category.value,
            criteria_failed=result.criteria_failed,
        )
        logger.info(
            EXECUTION_RECOVERY_COMPLETE,
            task_id=task_execution.task.id,
            strategy=self.STRATEGY_TYPE,
            can_reassign=result.can_reassign,
            retry_count=task_execution.retry_count,
            max_retries=task_execution.task.max_retries,
        )

        return result

    async def finalize(self, execution_id: str) -> None:
        """No-op -- fail-and-reassign has no post-resume state."""
        _ = execution_id

    def get_strategy_type(self) -> str:
        """Return the strategy type identifier."""
        return self.STRATEGY_TYPE
