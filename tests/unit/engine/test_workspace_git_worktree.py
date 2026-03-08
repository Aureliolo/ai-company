"""Tests for PlannerWorktreeStrategy (git worktree backend)."""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from ai_company.engine.errors import (
    WorkspaceCleanupError,
    WorkspaceLimitError,
    WorkspaceMergeError,
    WorkspaceSetupError,
)
from ai_company.engine.workspace.config import PlannerWorktreesConfig
from ai_company.engine.workspace.git_worktree import PlannerWorktreeStrategy
from ai_company.engine.workspace.models import (
    Workspace,
    WorkspaceRequest,
)
from ai_company.engine.workspace.protocol import (
    WorkspaceIsolationStrategy,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_config(
    *,
    max_concurrent_worktrees: int = 8,
) -> PlannerWorktreesConfig:
    return PlannerWorktreesConfig(
        max_concurrent_worktrees=max_concurrent_worktrees,
    )


def _make_strategy(
    *,
    config: PlannerWorktreesConfig | None = None,
    repo_root: Path = Path("/fake/repo"),
) -> PlannerWorktreeStrategy:
    return PlannerWorktreeStrategy(
        config=config or _make_config(),
        repo_root=repo_root,
    )


def _make_request(
    *,
    task_id: str = "task-1",
    agent_id: str = "agent-1",
    base_branch: str = "main",
) -> WorkspaceRequest:
    return WorkspaceRequest(
        task_id=task_id,
        agent_id=agent_id,
        base_branch=base_branch,
    )


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


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------


class TestProtocolConformance:
    """PlannerWorktreeStrategy satisfies WorkspaceIsolationStrategy."""

    @pytest.mark.unit
    def test_isinstance_check(self) -> None:
        """Strategy passes runtime protocol check."""
        strategy = _make_strategy()
        assert isinstance(strategy, WorkspaceIsolationStrategy)


# ---------------------------------------------------------------------------
# get_strategy_type
# ---------------------------------------------------------------------------


class TestGetStrategyType:
    """Tests for get_strategy_type method."""

    @pytest.mark.unit
    def test_returns_planner_worktrees(self) -> None:
        """Returns the correct strategy type string."""
        strategy = _make_strategy()
        assert strategy.get_strategy_type() == "planner_worktrees"


# ---------------------------------------------------------------------------
# setup_workspace
# ---------------------------------------------------------------------------


class TestSetupWorkspace:
    """Tests for setup_workspace method."""

    @pytest.mark.unit
    async def test_setup_creates_branch_and_worktree(self) -> None:
        """Setup creates git branch and worktree, returns Workspace."""
        strategy = _make_strategy()
        mock_run_git = AsyncMock(return_value=(0, "", ""))

        with patch.object(
            PlannerWorktreeStrategy,
            "_run_git",
            mock_run_git,
        ):
            ws = await strategy.setup_workspace(
                request=_make_request(),
            )

        assert ws.task_id == "task-1"
        assert ws.agent_id == "agent-1"
        assert ws.base_branch == "main"
        assert ws.branch_name == "workspace/task-1"
        assert ws.workspace_id  # non-empty UUID
        assert ws.worktree_path  # non-empty path
        assert ws.created_at  # ISO 8601 string

        # Should have called git branch and git worktree add
        assert mock_run_git.call_count == 2

    @pytest.mark.unit
    async def test_setup_at_limit_raises(self) -> None:
        """Setup raises WorkspaceLimitError when at max."""
        strategy = _make_strategy(
            config=_make_config(
                max_concurrent_worktrees=1,
            )
        )
        mock_run_git = AsyncMock(return_value=(0, "", ""))

        with patch.object(
            PlannerWorktreeStrategy,
            "_run_git",
            mock_run_git,
        ):
            await strategy.setup_workspace(
                request=_make_request(task_id="task-1"),
            )

            with pytest.raises(WorkspaceLimitError):
                await strategy.setup_workspace(
                    request=_make_request(task_id="task-2"),
                )

    @pytest.mark.unit
    async def test_setup_branch_failure_raises(self) -> None:
        """Setup raises WorkspaceSetupError on git branch failure."""
        strategy = _make_strategy()
        mock_run_git = AsyncMock(
            return_value=(1, "", "fatal: branch already exists"),
        )

        with (
            patch.object(
                PlannerWorktreeStrategy,
                "_run_git",
                mock_run_git,
            ),
            pytest.raises(WorkspaceSetupError),
        ):
            await strategy.setup_workspace(
                request=_make_request(),
            )

    @pytest.mark.unit
    async def test_setup_worktree_failure_raises(self) -> None:
        """Setup raises WorkspaceSetupError on worktree add failure."""
        strategy = _make_strategy()
        # First call (branch) succeeds, second (worktree add) fails
        mock_run_git = AsyncMock(
            side_effect=[
                (0, "", ""),
                (1, "", "fatal: worktree path already exists"),
            ],
        )

        with (
            patch.object(
                PlannerWorktreeStrategy,
                "_run_git",
                mock_run_git,
            ),
            pytest.raises(WorkspaceSetupError),
        ):
            await strategy.setup_workspace(
                request=_make_request(),
            )


# ---------------------------------------------------------------------------
# merge_workspace
# ---------------------------------------------------------------------------


class TestMergeWorkspace:
    """Tests for merge_workspace method."""

    @pytest.mark.unit
    async def test_merge_success(self) -> None:
        """Successful merge returns MergeResult(success=True)."""
        strategy = _make_strategy()
        ws = _make_workspace()
        # Register workspace so merge can find it
        strategy._active_workspaces[ws.workspace_id] = ws

        # checkout succeeds, merge succeeds, rev-parse returns SHA
        mock_run_git = AsyncMock(
            side_effect=[
                (0, "", ""),  # checkout base
                (0, "", ""),  # merge --no-ff
                (0, "abc123", ""),  # rev-parse HEAD
            ],
        )

        with patch.object(
            PlannerWorktreeStrategy,
            "_run_git",
            mock_run_git,
        ):
            result = await strategy.merge_workspace(workspace=ws)

        assert result.success is True
        assert result.conflicts == ()
        assert result.merged_commit_sha == "abc123"
        assert result.duration_seconds >= 0.0

    @pytest.mark.unit
    async def test_merge_with_conflict(self) -> None:
        """Merge conflict returns MergeResult(success=False)."""
        strategy = _make_strategy()
        ws = _make_workspace()
        strategy._active_workspaces[ws.workspace_id] = ws

        mock_run_git = AsyncMock(
            side_effect=[
                (0, "", ""),  # checkout base
                (1, "", "CONFLICT (content)"),  # merge fails
                (0, "src/main.py\n", ""),  # diff --name-only
                (0, "", ""),  # merge --abort
            ],
        )

        with patch.object(
            PlannerWorktreeStrategy,
            "_run_git",
            mock_run_git,
        ):
            result = await strategy.merge_workspace(workspace=ws)

        assert result.success is False
        assert len(result.conflicts) == 1
        assert result.conflicts[0].file_path == "src/main.py"
        assert result.merged_commit_sha is None

    @pytest.mark.unit
    async def test_merge_checkout_failure_raises(self) -> None:
        """Merge raises WorkspaceMergeError on checkout failure."""
        strategy = _make_strategy()
        ws = _make_workspace()
        strategy._active_workspaces[ws.workspace_id] = ws

        mock_run_git = AsyncMock(
            return_value=(1, "", "error: checkout failed"),
        )

        with (
            patch.object(
                PlannerWorktreeStrategy,
                "_run_git",
                mock_run_git,
            ),
            pytest.raises(WorkspaceMergeError),
        ):
            await strategy.merge_workspace(workspace=ws)


# ---------------------------------------------------------------------------
# teardown_workspace
# ---------------------------------------------------------------------------


class TestTeardownWorkspace:
    """Tests for teardown_workspace method."""

    @pytest.mark.unit
    async def test_teardown_removes_worktree_and_branch(self) -> None:
        """Teardown removes worktree, deletes branch, unregisters."""
        strategy = _make_strategy()
        ws = _make_workspace()
        strategy._active_workspaces[ws.workspace_id] = ws

        mock_run_git = AsyncMock(return_value=(0, "", ""))

        with patch.object(
            PlannerWorktreeStrategy,
            "_run_git",
            mock_run_git,
        ):
            await strategy.teardown_workspace(workspace=ws)

        # Should have called worktree remove and branch -d
        assert mock_run_git.call_count == 2
        assert ws.workspace_id not in strategy._active_workspaces

    @pytest.mark.unit
    async def test_teardown_worktree_failure_raises(self) -> None:
        """Teardown raises WorkspaceCleanupError on failure."""
        strategy = _make_strategy()
        ws = _make_workspace()
        strategy._active_workspaces[ws.workspace_id] = ws

        mock_run_git = AsyncMock(
            return_value=(1, "", "error: cannot remove"),
        )

        with (
            patch.object(
                PlannerWorktreeStrategy,
                "_run_git",
                mock_run_git,
            ),
            pytest.raises(WorkspaceCleanupError),
        ):
            await strategy.teardown_workspace(workspace=ws)


# ---------------------------------------------------------------------------
# list_active_workspaces
# ---------------------------------------------------------------------------


class TestListActiveWorkspaces:
    """Tests for list_active_workspaces method."""

    @pytest.mark.unit
    async def test_empty_initially(self) -> None:
        """No active workspaces at start."""
        strategy = _make_strategy()
        result = await strategy.list_active_workspaces()
        assert result == ()

    @pytest.mark.unit
    async def test_returns_registered_workspaces(self) -> None:
        """Returns all registered workspaces as a tuple."""
        strategy = _make_strategy()
        ws1 = _make_workspace(workspace_id="ws-1")
        ws2 = _make_workspace(workspace_id="ws-2")
        strategy._active_workspaces["ws-1"] = ws1
        strategy._active_workspaces["ws-2"] = ws2

        result = await strategy.list_active_workspaces()
        assert len(result) == 2
        ids = {w.workspace_id for w in result}
        assert ids == {"ws-1", "ws-2"}


# ---------------------------------------------------------------------------
# Concurrent setup
# ---------------------------------------------------------------------------


class TestConcurrentSetup:
    """Tests for concurrent workspace setup via lock."""

    @pytest.mark.unit
    async def test_concurrent_setup_respects_limit(self) -> None:
        """Two concurrent setups at limit=1: one succeeds, one fails."""
        import asyncio

        strategy = _make_strategy(
            config=_make_config(
                max_concurrent_worktrees=1,
            )
        )

        call_count = 0

        async def mock_git(
            self_: PlannerWorktreeStrategy,
            *args: str,
        ) -> tuple[int, str, str]:
            nonlocal call_count
            call_count += 1
            # Slow down first call to ensure overlap
            if call_count <= 2:
                await asyncio.sleep(0.01)
            return (0, "", "")

        results: list[Workspace | Exception] = []

        async def setup_one(task_id: str) -> None:
            try:
                ws = await strategy.setup_workspace(
                    request=_make_request(task_id=task_id),
                )
                results.append(ws)
            except Exception as exc:
                results.append(exc)

        with patch.object(
            PlannerWorktreeStrategy,
            "_run_git",
            side_effect=mock_git,
        ):
            await asyncio.gather(
                setup_one("task-1"),
                setup_one("task-2"),
            )

        successes = [r for r in results if isinstance(r, Workspace)]
        failures = [r for r in results if isinstance(r, WorkspaceLimitError)]
        assert len(successes) == 1
        assert len(failures) == 1
