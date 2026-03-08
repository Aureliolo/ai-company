"""Workspace isolation service.

High-level service that coordinates workspace lifecycle:
setup, merge, and teardown for groups of agent workspaces.
"""

import time
from typing import TYPE_CHECKING
from uuid import uuid4

from ai_company.engine.workspace.merge import MergeOrchestrator
from ai_company.engine.workspace.models import (
    Workspace,
    WorkspaceGroupResult,
)
from ai_company.observability import get_logger

if TYPE_CHECKING:
    from ai_company.engine.workspace.config import (
        WorkspaceIsolationConfig,
    )
    from ai_company.engine.workspace.models import WorkspaceRequest
    from ai_company.engine.workspace.protocol import (
        WorkspaceIsolationStrategy,
    )

logger = get_logger(__name__)


class WorkspaceIsolationService:
    """Service for managing workspace isolation lifecycle.

    Coordinates creating, merging, and tearing down workspaces
    for groups of concurrent agent tasks.

    Args:
        strategy: Workspace isolation strategy implementation.
        config: Workspace isolation configuration.
    """

    __slots__ = ("_config", "_merge_orchestrator", "_strategy")

    def __init__(
        self,
        *,
        strategy: WorkspaceIsolationStrategy,
        config: WorkspaceIsolationConfig,
    ) -> None:
        self._strategy = strategy
        self._config = config
        pw = config.planner_worktrees
        self._merge_orchestrator = MergeOrchestrator(
            strategy=strategy,
            merge_order=pw.merge_order,
            conflict_escalation=pw.conflict_escalation,
            cleanup_on_merge=pw.cleanup_on_merge,
        )

    async def setup_group(
        self,
        *,
        requests: tuple[WorkspaceRequest, ...],
    ) -> tuple[Workspace, ...]:
        """Create workspaces for a group of agent tasks.

        Args:
            requests: Workspace creation requests.

        Returns:
            Tuple of created workspaces.
        """
        workspaces: list[Workspace] = []
        for request in requests:
            ws = await self._strategy.setup_workspace(
                request=request,
            )
            workspaces.append(ws)
        return tuple(workspaces)

    async def merge_group(
        self,
        *,
        workspaces: tuple[Workspace, ...],
    ) -> WorkspaceGroupResult:
        """Merge all workspaces and return aggregated result.

        Args:
            workspaces: Workspaces to merge.

        Returns:
            Aggregated merge result for the group.
        """
        start = time.monotonic()
        merge_results = await self._merge_orchestrator.merge_all(
            workspaces=workspaces,
        )
        elapsed = time.monotonic() - start

        return WorkspaceGroupResult(
            group_id=str(uuid4()),
            merge_results=merge_results,
            duration_seconds=elapsed,
        )

    async def teardown_group(
        self,
        *,
        workspaces: tuple[Workspace, ...],
    ) -> None:
        """Tear down all workspaces in a group.

        Args:
            workspaces: Workspaces to tear down.
        """
        for workspace in workspaces:
            await self._strategy.teardown_workspace(
                workspace=workspace,
            )
