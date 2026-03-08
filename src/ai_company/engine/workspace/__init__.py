"""Workspace isolation for concurrent agent execution.

Provides git-worktree-based workspace isolation so multiple agents
can work on the same repository without interfering with each other.
"""

from ai_company.engine.workspace.config import (
    PlannerWorktreesConfig,
    WorkspaceIsolationConfig,
)
from ai_company.engine.workspace.git_worktree import (
    PlannerWorktreeStrategy,
)
from ai_company.engine.workspace.merge import MergeOrchestrator
from ai_company.engine.workspace.models import (
    MergeConflict,
    MergeResult,
    Workspace,
    WorkspaceGroupResult,
    WorkspaceRequest,
)
from ai_company.engine.workspace.protocol import (
    WorkspaceIsolationStrategy,
)
from ai_company.engine.workspace.service import (
    WorkspaceIsolationService,
)

__all__ = [
    "MergeConflict",
    "MergeOrchestrator",
    "MergeResult",
    "PlannerWorktreeStrategy",
    "PlannerWorktreesConfig",
    "Workspace",
    "WorkspaceGroupResult",
    "WorkspaceIsolationConfig",
    "WorkspaceIsolationService",
    "WorkspaceIsolationStrategy",
    "WorkspaceRequest",
]
