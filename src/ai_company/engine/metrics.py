"""Task completion metrics model.

Proxy overhead metrics for an agent run, computed from
``AgentRunResult`` data per DESIGN_SPEC §10.5 (M3).
"""

from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

from ai_company.core.types import NotBlankStr  # noqa: TC001

if TYPE_CHECKING:
    from ai_company.engine.run_result import AgentRunResult


class TaskCompletionMetrics(BaseModel):
    """Proxy overhead metrics for an agent run (DESIGN_SPEC §10.5).

    Computed from ``AgentRunResult`` after execution to surface
    orchestration overhead indicators (turns, tokens, cost, duration).

    Attributes:
        task_id: Task identifier (``None`` for future taskless runs).
        agent_id: Agent identifier (string form of UUID).
        turns_per_task: Number of LLM turns to complete the task.
        tokens_per_task: Total tokens consumed (input + output).
        cost_per_task: Total USD cost for the task.
        duration_seconds: Wall-clock execution time in seconds.
    """

    model_config = ConfigDict(frozen=True)

    task_id: NotBlankStr | None = Field(
        default=None,
        description="Task identifier",
    )
    agent_id: NotBlankStr = Field(description="Agent identifier")
    turns_per_task: int = Field(
        ge=0,
        description="Number of LLM turns to complete the task",
    )
    tokens_per_task: int = Field(
        ge=0,
        description="Total tokens consumed (input + output)",
    )
    cost_per_task: float = Field(
        ge=0.0,
        description="Total USD cost for the task",
    )
    duration_seconds: float = Field(
        ge=0.0,
        description="Wall-clock execution time in seconds",
    )
    prompt_tokens: int = Field(
        default=0,
        ge=0,
        description="Estimated system prompt tokens",
    )
    prompt_cost_ratio: float = Field(
        default=0.0,
        ge=0.0,
        description=("Ratio of prompt tokens to total tokens (overhead indicator)"),
    )

    @classmethod
    def from_run_result(cls, result: AgentRunResult) -> TaskCompletionMetrics:
        """Build metrics from an agent run result.

        Args:
            result: The ``AgentRunResult`` to extract metrics from.

        Returns:
            New ``TaskCompletionMetrics`` with values extracted from
            the result's execution context and metadata.
        """
        accumulated = result.execution_result.context.accumulated_cost
        prompt_tokens = result.system_prompt.estimated_tokens
        total_tokens = accumulated.total_tokens
        prompt_cost_ratio = prompt_tokens / total_tokens if total_tokens > 0 else 0.0
        return cls(
            task_id=result.task_id,
            agent_id=result.agent_id,
            turns_per_task=result.total_turns,
            tokens_per_task=total_tokens,
            cost_per_task=result.total_cost_usd,
            duration_seconds=result.duration_seconds,
            prompt_tokens=prompt_tokens,
            prompt_cost_ratio=prompt_cost_ratio,
        )
