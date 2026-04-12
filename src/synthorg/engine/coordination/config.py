"""Coordination configuration."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from synthorg.core.types import NotBlankStr  # noqa: TC001


class CoordinationConfig(BaseModel):
    """Configuration for a multi-agent coordination run.

    Attributes:
        max_concurrency_per_wave: Max parallel agents per wave
            (``None`` = unlimited).
        fail_fast: Stop on first wave failure instead of continuing.
        enable_workspace_isolation: Create isolated workspaces for
            multi-agent execution.
        base_branch: Git branch to use for workspace isolation.
        max_stall_count: Maximum consecutive stalls before escalation
            (used by ``MagenticReplanHook``).
        max_reset_count: Maximum replan cycles before escalation
            (used by ``MagenticReplanHook``).
        replan_strategy: Replan hook implementation to use.
        orchestrator_strategy: Subtask selection strategy within
            ``CentralizedDispatcher``.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    max_concurrency_per_wave: int | None = Field(
        default=None,
        ge=1,
        description="Max parallel agents per wave (None = unlimited)",
    )
    fail_fast: bool = Field(
        default=False,
        description="Stop on first wave failure",
    )
    enable_workspace_isolation: bool = Field(
        default=True,
        description="Create isolated workspaces for multi-agent execution",
    )
    base_branch: NotBlankStr = Field(
        default="main",
        description="Git branch for workspace isolation",
    )
    max_stall_count: int = Field(
        default=3,
        ge=1,
        description="Max consecutive stalls before escalation",
    )
    max_reset_count: int = Field(
        default=2,
        ge=1,
        description="Max replan cycles before escalation",
    )
    replan_strategy: Literal["noop", "magentic"] = Field(
        default="noop",
        description="Replan hook implementation",
    )
    orchestrator_strategy: Literal["naive", "magentic_dynamic"] = Field(
        default="naive",
        description="Subtask selection strategy for centralized dispatch",
    )
