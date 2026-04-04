"""Unit tests for RecoveryResult failure diagnosis fields and infer_failure_category."""

import pytest
from pydantic import ValidationError

from synthorg.core.enums import FailureCategory, TaskStatus
from synthorg.core.task import Task
from synthorg.engine.context import AgentContext
from synthorg.engine.recovery import RecoveryResult, infer_failure_category
from synthorg.engine.stagnation.models import StagnationResult, StagnationVerdict


def _make_recovery_result(  # noqa: PLR0913
    ctx: AgentContext,
    *,
    failure_category: FailureCategory = FailureCategory.TOOL_FAILURE,
    failure_context: dict[str, object] | None = None,
    criteria_failed: tuple[str, ...] = (),
    stagnation_evidence: StagnationResult | None = None,
    checkpoint_context_json: str | None = None,
    resume_attempt: int = 0,
) -> RecoveryResult:
    """Build a RecoveryResult from an AgentContext with FAILED execution."""
    assert ctx.task_execution is not None
    failed = ctx.task_execution.with_transition(
        TaskStatus.FAILED, reason="test failure"
    )
    return RecoveryResult(
        task_execution=failed,
        strategy_type="fail_reassign",
        context_snapshot=ctx.to_snapshot(),
        error_message="test failure",
        failure_category=failure_category,
        failure_context=failure_context if failure_context is not None else {},
        criteria_failed=criteria_failed,
        stagnation_evidence=stagnation_evidence,
        checkpoint_context_json=checkpoint_context_json,
        resume_attempt=resume_attempt,
    )


@pytest.mark.unit
class TestRecoveryResultDiagnosisFields:
    """Tests for the new failure diagnosis fields on RecoveryResult."""

    def test_failure_category_required(
        self,
        sample_agent_context: AgentContext,
        sample_task_with_criteria: Task,
    ) -> None:
        """failure_category is required -- omitting it raises ValidationError."""
        ctx = sample_agent_context.with_task_transition(
            TaskStatus.IN_PROGRESS, reason="starting"
        )
        assert ctx.task_execution is not None
        failed = ctx.task_execution.with_transition(TaskStatus.FAILED, reason="crash")
        with pytest.raises(ValidationError, match="failure_category"):
            RecoveryResult(
                task_execution=failed,
                strategy_type="fail_reassign",
                context_snapshot=ctx.to_snapshot(),
                error_message="crash",
                failure_context={},
            )

    def test_failure_context_required(
        self,
        sample_agent_context: AgentContext,
        sample_task_with_criteria: Task,
    ) -> None:
        """failure_context is required -- omitting it raises ValidationError."""
        ctx = sample_agent_context.with_task_transition(
            TaskStatus.IN_PROGRESS, reason="starting"
        )
        assert ctx.task_execution is not None
        failed = ctx.task_execution.with_transition(TaskStatus.FAILED, reason="crash")
        with pytest.raises(ValidationError, match="failure_context"):
            RecoveryResult(
                task_execution=failed,
                strategy_type="fail_reassign",
                context_snapshot=ctx.to_snapshot(),
                error_message="crash",
                failure_category=FailureCategory.TOOL_FAILURE,
            )

    def test_all_fields_populated(
        self,
        sample_agent_context: AgentContext,
    ) -> None:
        """All diagnosis fields can be populated together."""
        ctx = sample_agent_context.with_task_transition(
            TaskStatus.IN_PROGRESS, reason="starting"
        )
        stag = StagnationResult(
            verdict=StagnationVerdict.TERMINATE,
            repetition_ratio=0.8,
            cycle_length=3,
        )
        result = _make_recovery_result(
            ctx,
            failure_category=FailureCategory.STAGNATION,
            failure_context={"detector": "tool_repetition"},
            criteria_failed=("Login endpoint returns JWT token",),
            stagnation_evidence=stag,
        )
        assert result.failure_category is FailureCategory.STAGNATION
        assert result.failure_context == {"detector": "tool_repetition"}
        assert result.criteria_failed == ("Login endpoint returns JWT token",)
        assert result.stagnation_evidence is not None
        assert result.stagnation_evidence.repetition_ratio == 0.8

    def test_criteria_failed_defaults_empty(
        self,
        sample_agent_context: AgentContext,
    ) -> None:
        """criteria_failed defaults to empty tuple."""
        ctx = sample_agent_context.with_task_transition(
            TaskStatus.IN_PROGRESS, reason="starting"
        )
        result = _make_recovery_result(ctx)
        assert result.criteria_failed == ()

    def test_stagnation_evidence_defaults_none(
        self,
        sample_agent_context: AgentContext,
    ) -> None:
        """stagnation_evidence defaults to None."""
        ctx = sample_agent_context.with_task_transition(
            TaskStatus.IN_PROGRESS, reason="starting"
        )
        result = _make_recovery_result(ctx)
        assert result.stagnation_evidence is None

    def test_failure_context_deep_copied(
        self,
        sample_agent_context: AgentContext,
    ) -> None:
        """Mutating the original dict does not affect the frozen model."""
        ctx = sample_agent_context.with_task_transition(
            TaskStatus.IN_PROGRESS, reason="starting"
        )
        nested: dict[str, int] = {"a": 1}
        original: dict[str, object] = {"key": "value", "nested": nested}
        result = _make_recovery_result(ctx, failure_context=original)
        original["key"] = "mutated"
        nested["a"] = 999
        assert result.failure_context["key"] == "value"
        nested_copy = result.failure_context["nested"]
        assert isinstance(nested_copy, dict)
        assert nested_copy["a"] == 1

    def test_frozen(
        self,
        sample_agent_context: AgentContext,
    ) -> None:
        """Attempting to set fields on a constructed result raises."""
        ctx = sample_agent_context.with_task_transition(
            TaskStatus.IN_PROGRESS, reason="starting"
        )
        result = _make_recovery_result(ctx)
        with pytest.raises(ValidationError):
            result.failure_category = FailureCategory.TIMEOUT  # type: ignore[misc]


@pytest.mark.unit
class TestInferFailureCategory:
    """Tests for the infer_failure_category helper."""

    @pytest.mark.parametrize(
        ("error_message", "expected"),
        [
            pytest.param(
                "Budget limit exceeded for task",
                FailureCategory.BUDGET_EXCEEDED,
                id="budget",
            ),
            pytest.param(
                "Monthly BUDGET exhausted",
                FailureCategory.BUDGET_EXCEEDED,
                id="budget-upper",
            ),
            pytest.param(
                "Connection timeout to provider",
                FailureCategory.TIMEOUT,
                id="timeout",
            ),
            pytest.param(
                "Request timed out after 30s",
                FailureCategory.TIMEOUT,
                id="timed-out",
            ),
            pytest.param(
                "Stagnation detected: repetitive tool calls",
                FailureCategory.STAGNATION,
                id="stagnation",
            ),
            pytest.param(
                "Delegation failed: no capable agent",
                FailureCategory.DELEGATION_FAILED,
                id="delegation",
            ),
            pytest.param(
                "Quality gate failed: criteria not met",
                FailureCategory.QUALITY_GATE_FAILED,
                id="quality",
            ),
            pytest.param(
                "Acceptance criteria not satisfied",
                FailureCategory.QUALITY_GATE_FAILED,
                id="criteria",
            ),
            pytest.param(
                "Unknown error: something went wrong",
                FailureCategory.TOOL_FAILURE,
                id="unknown-default",
            ),
            pytest.param(
                "NullPointerException in tool handler",
                FailureCategory.TOOL_FAILURE,
                id="generic-error",
            ),
        ],
    )
    def test_keyword_mapping(
        self, error_message: str, expected: FailureCategory
    ) -> None:
        """Each keyword maps to the correct category."""
        assert infer_failure_category(error_message) == expected
