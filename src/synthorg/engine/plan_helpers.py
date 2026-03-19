"""Shared plan utilities for plan-based execution loops.

Stateless helpers used by both ``PlanExecuteLoop`` and ``HybridLoop``
for common plan-step operations.
"""

from typing import TYPE_CHECKING

from synthorg.providers.enums import FinishReason, MessageRole

if TYPE_CHECKING:
    from synthorg.engine.context import AgentContext
    from synthorg.providers.models import CompletionResponse

    from .plan_models import ExecutionPlan, StepStatus


def update_step_status(
    plan: ExecutionPlan,
    step_idx: int,
    status: StepStatus,
) -> ExecutionPlan:
    """Return a new plan with the given step's status updated.

    Args:
        plan: The current execution plan (frozen).
        step_idx: Zero-based index of the step to update.
        status: New status for the step.

    Returns:
        A copy of *plan* with the step at *step_idx* updated.
    """
    steps = list(plan.steps)
    steps[step_idx] = steps[step_idx].model_copy(
        update={"status": status},
    )
    return plan.model_copy(update={"steps": tuple(steps)})


def extract_task_summary(ctx: AgentContext) -> str:
    """Extract a task summary from the context.

    Uses the task title when available, otherwise the first user
    message.  Truncates to 200 characters.

    Args:
        ctx: Agent context to extract from.

    Returns:
        A short summary string.
    """
    if ctx.task_execution is not None:
        return ctx.task_execution.task.title[:200]
    for msg in ctx.conversation:
        if msg.role == MessageRole.USER and msg.content:
            return msg.content[:200]
    return "task"


def assess_step_success(response: CompletionResponse) -> bool:
    """Determine if a step completed successfully.

    A step is considered successful when the LLM terminates
    normally (STOP or MAX_TOKENS).  MAX_TOKENS is treated as
    success because the step instruction asks the LLM to summarize
    its work; a truncated summary still represents a completed
    step for planning purposes.

    Args:
        response: The LLM completion response for the step.

    Returns:
        ``True`` when the step is considered successful.
    """
    return response.finish_reason in (
        FinishReason.STOP,
        FinishReason.MAX_TOKENS,
    )
