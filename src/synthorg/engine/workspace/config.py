"""Workspace isolation configuration models."""

from pydantic import BaseModel, ConfigDict, Field

from synthorg.core.enums import ConflictEscalation, MergeOrder
from synthorg.core.types import NotBlankStr  # noqa: TC001


class SemanticAnalysisConfig(BaseModel):
    """Configuration for semantic conflict detection after merge.

    Attributes:
        enabled: Whether semantic analysis runs after merge.
        file_extensions: File extensions to analyze.
        max_files: Maximum files to analyze per merge.
        llm_model: Model for LLM-based semantic analysis.
        llm_temperature: Temperature for LLM analysis.
        llm_max_tokens: Maximum tokens for LLM response.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    enabled: bool = Field(
        default=False,
        description="Whether semantic analysis runs after merge",
    )
    file_extensions: tuple[str, ...] = Field(
        default=(".py",),
        description="File extensions to analyze",
    )
    max_files: int = Field(
        default=50,
        ge=1,
        le=200,
        description="Maximum files to analyze per merge",
    )
    llm_model: NotBlankStr | None = Field(
        default=None,
        description="Model for LLM-based semantic analysis",
    )
    llm_temperature: float = Field(
        default=0.1,
        ge=0.0,
        le=2.0,
        description="Temperature for LLM analysis",
    )
    llm_max_tokens: int = Field(
        default=4096,
        gt=0,
        description="Maximum tokens for LLM response",
    )


class PlannerWorktreesConfig(BaseModel):
    """Configuration for the planner-worktrees isolation strategy.

    Attributes:
        max_concurrent_worktrees: Maximum number of active worktrees.
        merge_order: Order in which branches are merged back.
        conflict_escalation: Strategy for handling merge conflicts.
        worktree_base_dir: Base directory for worktree creation.
        cleanup_on_merge: Whether to remove worktree after merge.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    max_concurrent_worktrees: int = Field(
        default=8,
        ge=1,
        le=32,
        description="Maximum number of active worktrees",
    )
    merge_order: MergeOrder = Field(
        default=MergeOrder.COMPLETION,
        description="Order in which branches are merged back",
    )
    conflict_escalation: ConflictEscalation = Field(
        default=ConflictEscalation.HUMAN,
        description="Strategy for handling merge conflicts",
    )
    worktree_base_dir: NotBlankStr | None = Field(
        default=None,
        description="Base directory for worktree creation",
    )
    cleanup_on_merge: bool = Field(
        default=True,
        description="Whether to remove worktree after merge",
    )
    semantic_analysis: SemanticAnalysisConfig = Field(
        default_factory=SemanticAnalysisConfig,
        description="Semantic conflict detection configuration",
    )


class WorkspaceIsolationConfig(BaseModel):
    """Top-level workspace isolation configuration.

    Attributes:
        strategy: Name of the isolation strategy to use.
        planner_worktrees: Config for planner-worktrees strategy.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    strategy: NotBlankStr = Field(
        default="planner_worktrees",
        description="Name of the isolation strategy",
    )
    planner_worktrees: PlannerWorktreesConfig = Field(
        default_factory=PlannerWorktreesConfig,
        description="Config for planner-worktrees strategy",
    )
