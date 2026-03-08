"""Merge orchestrator for workspace branches.

Sequences workspace merges according to the configured merge order
and handles conflict escalation.
"""

from typing import TYPE_CHECKING

from ai_company.core.enums import ConflictEscalation, MergeOrder
from ai_company.observability import get_logger
from ai_company.observability.events.workspace import (
    WORKSPACE_GROUP_MERGE_COMPLETE,
    WORKSPACE_GROUP_MERGE_START,
)

if TYPE_CHECKING:
    from ai_company.engine.workspace.models import (
        MergeResult,
        Workspace,
    )
    from ai_company.engine.workspace.protocol import (
        WorkspaceIsolationStrategy,
    )

logger = get_logger(__name__)


class MergeOrchestrator:
    """Orchestrates sequential merging of workspace branches.

    Merges are always sequential (critical for git state consistency).
    The merge order and conflict escalation strategy are configurable.

    Args:
        strategy: Workspace isolation strategy for merge operations.
        merge_order: Order in which workspaces are merged.
        conflict_escalation: How to handle merge conflicts.
        cleanup_on_merge: Whether to teardown after successful merge.
    """

    __slots__ = (
        "_cleanup_on_merge",
        "_conflict_escalation",
        "_merge_order",
        "_strategy",
    )

    def __init__(
        self,
        *,
        strategy: WorkspaceIsolationStrategy,
        merge_order: MergeOrder,
        conflict_escalation: ConflictEscalation,
        cleanup_on_merge: bool = True,
    ) -> None:
        self._strategy = strategy
        self._merge_order = merge_order
        self._conflict_escalation = conflict_escalation
        self._cleanup_on_merge = cleanup_on_merge

    async def merge_all(
        self,
        *,
        workspaces: tuple[Workspace, ...],
        completion_order: tuple[str, ...] | None = None,
        priority_order: tuple[str, ...] | None = None,
    ) -> tuple[MergeResult, ...]:
        """Merge all workspaces sequentially in configured order.

        Args:
            workspaces: Workspaces to merge.
            completion_order: Workspace IDs in completion order.
            priority_order: Workspace IDs in priority order.

        Returns:
            Tuple of merge results (may be partial on HUMAN stop).
        """
        ordered = self._sort_workspaces(
            workspaces=workspaces,
            completion_order=completion_order,
            priority_order=priority_order,
        )

        logger.info(
            WORKSPACE_GROUP_MERGE_START,
            count=len(ordered),
            merge_order=self._merge_order.value,
        )

        results: list[MergeResult] = []
        for workspace in ordered:
            result = await self._strategy.merge_workspace(
                workspace=workspace,
            )

            if not result.success:
                result = result.model_copy(
                    update={
                        "escalation": self._conflict_escalation.value,
                    },
                )
                results.append(result)

                if self._conflict_escalation == ConflictEscalation.HUMAN:
                    # Stop on conflict with HUMAN escalation
                    break
                # REVIEW_AGENT: flag and continue
                continue

            results.append(result)

            if self._cleanup_on_merge:
                await self._strategy.teardown_workspace(
                    workspace=workspace,
                )

        logger.info(
            WORKSPACE_GROUP_MERGE_COMPLETE,
            total=len(results),
            successful=sum(1 for r in results if r.success),
        )
        return tuple(results)

    def _sort_workspaces(
        self,
        *,
        workspaces: tuple[Workspace, ...],
        completion_order: tuple[str, ...] | None,
        priority_order: tuple[str, ...] | None,
    ) -> tuple[Workspace, ...]:
        """Sort workspaces according to the configured merge order.

        Args:
            workspaces: Workspaces to sort.
            completion_order: Workspace IDs in completion order.
            priority_order: Workspace IDs in priority order.

        Returns:
            Sorted tuple of workspaces.
        """
        ws_map = {w.workspace_id: w for w in workspaces}

        if self._merge_order == MergeOrder.COMPLETION:
            if completion_order:
                return tuple(ws_map[wid] for wid in completion_order if wid in ws_map)
            return workspaces

        if self._merge_order == MergeOrder.PRIORITY:
            if priority_order:
                return tuple(ws_map[wid] for wid in priority_order if wid in ws_map)
            return workspaces

        # MANUAL: as given
        return workspaces
