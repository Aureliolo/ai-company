"""Tests for MergeOrchestrator."""

from unittest.mock import AsyncMock

import pytest

from ai_company.core.enums import ConflictEscalation, MergeOrder
from ai_company.engine.workspace.merge import MergeOrchestrator
from ai_company.engine.workspace.models import (
    MergeConflict,
    MergeResult,
    Workspace,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_workspace(  # noqa: PLR0913
    *,
    workspace_id: str = "ws-001",
    task_id: str = "task-1",
    agent_id: str = "agent-1",
    branch_name: str = "workspace/task-1",
    worktree_path: str = "fake/worktrees/ws-001",
    base_branch: str = "main",
    created_at: str = "2026-03-08T00:00:00+00:00",
) -> Workspace:
    return Workspace(
        workspace_id=workspace_id,
        task_id=task_id,
        agent_id=agent_id,
        branch_name=branch_name,
        worktree_path=worktree_path,
        base_branch=base_branch,
        created_at=created_at,
    )


def _make_merge_result(  # noqa: PLR0913
    *,
    workspace_id: str = "ws-001",
    branch_name: str = "workspace/task-1",
    success: bool = True,
    conflicts: tuple[MergeConflict, ...] = (),
    duration_seconds: float = 0.5,
    merged_commit_sha: str | None = "abc123",
) -> MergeResult:
    return MergeResult(
        workspace_id=workspace_id,
        branch_name=branch_name,
        success=success,
        conflicts=conflicts,
        duration_seconds=duration_seconds,
        merged_commit_sha=merged_commit_sha,
    )


def _make_conflict(
    *,
    file_path: str = "src/a.py",
) -> MergeConflict:
    return MergeConflict(
        file_path=file_path,
        conflict_type="textual",
    )


def _make_orchestrator(
    *,
    strategy: AsyncMock | None = None,
    merge_order: MergeOrder = MergeOrder.COMPLETION,
    conflict_escalation: ConflictEscalation = ConflictEscalation.HUMAN,
    cleanup_on_merge: bool = True,
) -> MergeOrchestrator:
    return MergeOrchestrator(
        strategy=strategy or AsyncMock(),
        merge_order=merge_order,
        conflict_escalation=conflict_escalation,
        cleanup_on_merge=cleanup_on_merge,
    )


# ---------------------------------------------------------------------------
# Completion-order merging
# ---------------------------------------------------------------------------


class TestCompletionOrderMerge:
    """Tests for completion-order merge orchestration."""

    @pytest.mark.unit
    async def test_merge_all_completion_order(self) -> None:
        """Workspaces merge in completion order."""
        ws1 = _make_workspace(workspace_id="ws-1", task_id="task-1")
        ws2 = _make_workspace(workspace_id="ws-2", task_id="task-2")

        mock_strategy = AsyncMock()
        mock_strategy.merge_workspace = AsyncMock(
            side_effect=[
                _make_merge_result(workspace_id="ws-1"),
                _make_merge_result(workspace_id="ws-2"),
            ],
        )
        mock_strategy.teardown_workspace = AsyncMock()

        orch = _make_orchestrator(strategy=mock_strategy)
        results = await orch.merge_all(
            workspaces=(ws1, ws2),
            completion_order=("ws-1", "ws-2"),
        )

        assert len(results) == 2
        assert results[0].workspace_id == "ws-1"
        assert results[1].workspace_id == "ws-2"
        assert all(r.success for r in results)

    @pytest.mark.unit
    async def test_cleanup_called_after_success(self) -> None:
        """Teardown is called after each successful merge."""
        ws = _make_workspace(workspace_id="ws-1")
        mock_strategy = AsyncMock()
        mock_strategy.merge_workspace = AsyncMock(
            return_value=_make_merge_result(workspace_id="ws-1"),
        )
        mock_strategy.teardown_workspace = AsyncMock()

        orch = _make_orchestrator(
            strategy=mock_strategy,
            cleanup_on_merge=True,
        )
        await orch.merge_all(
            workspaces=(ws,),
            completion_order=("ws-1",),
        )

        mock_strategy.teardown_workspace.assert_called_once_with(
            workspace=ws,
        )

    @pytest.mark.unit
    async def test_no_cleanup_when_disabled(self) -> None:
        """Teardown is not called when cleanup_on_merge is False."""
        ws = _make_workspace(workspace_id="ws-1")
        mock_strategy = AsyncMock()
        mock_strategy.merge_workspace = AsyncMock(
            return_value=_make_merge_result(workspace_id="ws-1"),
        )
        mock_strategy.teardown_workspace = AsyncMock()

        orch = _make_orchestrator(
            strategy=mock_strategy,
            cleanup_on_merge=False,
        )
        await orch.merge_all(
            workspaces=(ws,),
            completion_order=("ws-1",),
        )

        mock_strategy.teardown_workspace.assert_not_called()


# ---------------------------------------------------------------------------
# Priority-order merging
# ---------------------------------------------------------------------------


class TestPriorityOrderMerge:
    """Tests for priority-order merge orchestration."""

    @pytest.mark.unit
    async def test_merge_all_priority_order(self) -> None:
        """Workspaces merge in priority order."""
        ws1 = _make_workspace(workspace_id="ws-1", task_id="task-1")
        ws2 = _make_workspace(workspace_id="ws-2", task_id="task-2")

        mock_strategy = AsyncMock()
        mock_strategy.merge_workspace = AsyncMock(
            side_effect=[
                _make_merge_result(workspace_id="ws-2"),
                _make_merge_result(workspace_id="ws-1"),
            ],
        )
        mock_strategy.teardown_workspace = AsyncMock()

        orch = _make_orchestrator(
            strategy=mock_strategy,
            merge_order=MergeOrder.PRIORITY,
        )
        # Priority order: ws-2 before ws-1
        results = await orch.merge_all(
            workspaces=(ws1, ws2),
            priority_order=("ws-2", "ws-1"),
        )

        assert len(results) == 2
        assert results[0].workspace_id == "ws-2"
        assert results[1].workspace_id == "ws-1"


# ---------------------------------------------------------------------------
# Conflict escalation
# ---------------------------------------------------------------------------


class TestConflictEscalation:
    """Tests for conflict handling during merge."""

    @pytest.mark.unit
    async def test_human_escalation_stops_on_conflict(self) -> None:
        """HUMAN escalation stops merging on first conflict."""
        ws1 = _make_workspace(workspace_id="ws-1", task_id="task-1")
        ws2 = _make_workspace(workspace_id="ws-2", task_id="task-2")

        conflict = _make_conflict()
        mock_strategy = AsyncMock()
        mock_strategy.merge_workspace = AsyncMock(
            side_effect=[
                _make_merge_result(
                    workspace_id="ws-1",
                    success=False,
                    conflicts=(conflict,),
                    merged_commit_sha=None,
                ),
                _make_merge_result(workspace_id="ws-2"),
            ],
        )
        mock_strategy.teardown_workspace = AsyncMock()

        orch = _make_orchestrator(
            strategy=mock_strategy,
            conflict_escalation=ConflictEscalation.HUMAN,
        )
        results = await orch.merge_all(
            workspaces=(ws1, ws2),
            completion_order=("ws-1", "ws-2"),
        )

        # Should stop after first conflict
        assert len(results) == 1
        assert results[0].success is False
        assert results[0].escalation == "human"

    @pytest.mark.unit
    async def test_review_agent_continues_on_conflict(self) -> None:
        """REVIEW_AGENT escalation flags conflict and continues."""
        ws1 = _make_workspace(workspace_id="ws-1", task_id="task-1")
        ws2 = _make_workspace(workspace_id="ws-2", task_id="task-2")

        conflict = _make_conflict()
        mock_strategy = AsyncMock()
        mock_strategy.merge_workspace = AsyncMock(
            side_effect=[
                _make_merge_result(
                    workspace_id="ws-1",
                    success=False,
                    conflicts=(conflict,),
                    merged_commit_sha=None,
                ),
                _make_merge_result(workspace_id="ws-2"),
            ],
        )
        mock_strategy.teardown_workspace = AsyncMock()

        orch = _make_orchestrator(
            strategy=mock_strategy,
            conflict_escalation=ConflictEscalation.REVIEW_AGENT,
        )
        results = await orch.merge_all(
            workspaces=(ws1, ws2),
            completion_order=("ws-1", "ws-2"),
        )

        # Should continue past conflict
        assert len(results) == 2
        assert results[0].success is False
        assert results[0].escalation == "review_agent"
        assert results[1].success is True


# ---------------------------------------------------------------------------
# Manual-order merging
# ---------------------------------------------------------------------------


class TestManualOrderMerge:
    """Tests for manual-order (as-given) merge."""

    @pytest.mark.unit
    async def test_merge_all_manual_order(self) -> None:
        """Manual order uses workspaces as given."""
        ws1 = _make_workspace(workspace_id="ws-1")
        ws2 = _make_workspace(workspace_id="ws-2")

        mock_strategy = AsyncMock()
        mock_strategy.merge_workspace = AsyncMock(
            side_effect=[
                _make_merge_result(workspace_id="ws-1"),
                _make_merge_result(workspace_id="ws-2"),
            ],
        )
        mock_strategy.teardown_workspace = AsyncMock()

        orch = _make_orchestrator(
            strategy=mock_strategy,
            merge_order=MergeOrder.MANUAL,
        )
        results = await orch.merge_all(workspaces=(ws1, ws2))

        assert len(results) == 2
        assert results[0].workspace_id == "ws-1"
        assert results[1].workspace_id == "ws-2"
