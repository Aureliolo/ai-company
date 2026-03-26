"""Integration tests for semantic conflict detection with real git repos.

Creates temporary git repositories with parallel workspace branches
that produce semantic conflicts when merged.
"""

import subprocess
from pathlib import Path

import pytest

from synthorg.core.enums import ConflictType
from synthorg.engine.workspace.config import (
    PlannerWorktreesConfig,
    SemanticAnalysisConfig,
)
from synthorg.engine.workspace.git_worktree import PlannerWorktreeStrategy
from synthorg.engine.workspace.models import WorkspaceRequest
from synthorg.engine.workspace.semantic_analyzer import AstSemanticAnalyzer

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _init_test_repo(repo_path: Path) -> None:
    """Initialize a git repository with an initial commit."""
    repo_path.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "init", "--initial-branch=main"],  # noqa: S607
        cwd=str(repo_path),
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],  # noqa: S607
        cwd=str(repo_path),
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],  # noqa: S607
        cwd=str(repo_path),
        check=True,
        capture_output=True,
    )
    readme = repo_path / "README.md"
    readme.write_text("# Test Repo\n")
    subprocess.run(
        ["git", "add", "."],  # noqa: S607
        cwd=str(repo_path),
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],  # noqa: S607
        cwd=str(repo_path),
        check=True,
        capture_output=True,
    )


def _commit_file(
    repo_path: Path,
    filename: str,
    content: str,
    message: str,
) -> None:
    """Create/update a file and commit it."""
    filepath = repo_path / filename
    filepath.parent.mkdir(parents=True, exist_ok=True)
    filepath.write_text(content)
    subprocess.run(  # noqa: S603
        ["git", "add", filename],  # noqa: S607
        cwd=str(repo_path),
        check=True,
        capture_output=True,
    )
    subprocess.run(  # noqa: S603
        ["git", "commit", "-m", message],  # noqa: S607
        cwd=str(repo_path),
        check=True,
        capture_output=True,
    )


def _make_strategy(
    repo_path: Path,
    *,
    semantic_enabled: bool = True,
) -> PlannerWorktreeStrategy:
    """Create a strategy with optional semantic analysis."""
    config = PlannerWorktreesConfig(
        max_concurrent_worktrees=8,
        semantic_analysis=SemanticAnalysisConfig(enabled=semantic_enabled),
    )
    analyzer = (
        AstSemanticAnalyzer(config=config.semantic_analysis)
        if semantic_enabled
        else None
    )
    return PlannerWorktreeStrategy(
        config=config,
        repo_root=repo_path,
        semantic_analyzer=analyzer,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSemanticConflictDetection:
    """Integration tests for semantic conflict detection after merge."""

    async def test_renamed_function_detected(self, tmp_path: Path) -> None:
        """Agent A renames function, Agent B calls old name -> semantic conflict."""
        repo = tmp_path / "repo"
        _init_test_repo(repo)

        # Create initial file with function
        _commit_file(
            repo,
            "utils.py",
            "def calculate_total(items):\n    return sum(items)\n",
            "Add utils",
        )

        strategy = _make_strategy(repo)

        # Agent A: rename function
        ws_a = await strategy.setup_workspace(
            request=WorkspaceRequest(
                task_id="rename-task",
                agent_id="agent-a",
            ),
        )
        _commit_file(
            Path(ws_a.worktree_path),
            "utils.py",
            "def compute_total(items):\n    return sum(items)\n",
            "Rename calculate_total to compute_total",
        )

        # Agent B: add caller using old name
        ws_b = await strategy.setup_workspace(
            request=WorkspaceRequest(
                task_id="caller-task",
                agent_id="agent-b",
            ),
        )
        _commit_file(
            Path(ws_b.worktree_path),
            "orders.py",
            (
                "from utils import calculate_total\n"
                "\nresult = calculate_total([1, 2, 3])\n"
            ),
            "Add orders module using calculate_total",
        )

        # Merge A first (succeeds, no conflicts)
        result_a = await strategy.merge_workspace(workspace=ws_a)
        assert result_a.success is True
        assert result_a.semantic_conflicts == ()

        # Merge B (succeeds textually, but has semantic conflict)
        result_b = await strategy.merge_workspace(workspace=ws_b)
        assert result_b.success is True
        assert len(result_b.semantic_conflicts) >= 1
        assert any(
            c.conflict_type == ConflictType.SEMANTIC
            for c in result_b.semantic_conflicts
        )
        assert any(
            "calculate_total" in c.description for c in result_b.semantic_conflicts
        )

        # Cleanup
        await strategy.teardown_workspace(workspace=ws_a)
        await strategy.teardown_workspace(workspace=ws_b)

    async def test_no_semantic_conflict_on_clean_merge(
        self,
        tmp_path: Path,
    ) -> None:
        """Different files, no semantic issues -> no conflicts."""
        repo = tmp_path / "repo"
        _init_test_repo(repo)

        strategy = _make_strategy(repo)

        # Agent A: add one file
        ws_a = await strategy.setup_workspace(
            request=WorkspaceRequest(
                task_id="task-a",
                agent_id="agent-a",
            ),
        )
        _commit_file(
            Path(ws_a.worktree_path),
            "module_a.py",
            "def func_a():\n    return 1\n",
            "Add module_a",
        )

        # Agent B: add a different file
        ws_b = await strategy.setup_workspace(
            request=WorkspaceRequest(
                task_id="task-b",
                agent_id="agent-b",
            ),
        )
        _commit_file(
            Path(ws_b.worktree_path),
            "module_b.py",
            "def func_b():\n    return 2\n",
            "Add module_b",
        )

        result_a = await strategy.merge_workspace(workspace=ws_a)
        assert result_a.success is True
        assert result_a.semantic_conflicts == ()

        result_b = await strategy.merge_workspace(workspace=ws_b)
        assert result_b.success is True
        assert result_b.semantic_conflicts == ()

        await strategy.teardown_workspace(workspace=ws_a)
        await strategy.teardown_workspace(workspace=ws_b)

    async def test_duplicate_definition_detected(
        self,
        tmp_path: Path,
    ) -> None:
        """Two agents add same function name to same file -> duplicate."""
        repo = tmp_path / "repo"
        _init_test_repo(repo)

        _commit_file(
            repo,
            "helpers.py",
            "# helpers module\n",
            "Add helpers stub",
        )

        strategy = _make_strategy(repo)

        # Agent A: add process function
        ws_a = await strategy.setup_workspace(
            request=WorkspaceRequest(
                task_id="task-a",
                agent_id="agent-a",
            ),
        )
        _commit_file(
            Path(ws_a.worktree_path),
            "helpers.py",
            ("# helpers module\n\ndef process(data):\n    return data.upper()\n"),
            "Add process function (agent A)",
        )

        # Agent B: also add process function with different impl
        ws_b = await strategy.setup_workspace(
            request=WorkspaceRequest(
                task_id="task-b",
                agent_id="agent-b",
            ),
        )
        _commit_file(
            Path(ws_b.worktree_path),
            "helpers.py",
            ("# helpers module\n\ndef process(data):\n    return data.lower()\n"),
            "Add process function (agent B)",
        )

        # Merge A
        result_a = await strategy.merge_workspace(workspace=ws_a)
        assert result_a.success is True

        # Merge B -- may cause textual conflict (same lines) or succeed
        # with duplicate definition. Either way, semantic analysis should
        # catch it if the merge succeeds.
        result_b = await strategy.merge_workspace(workspace=ws_b)
        if result_b.success:
            # Textual merge succeeded but we have duplicate definitions
            assert len(result_b.semantic_conflicts) >= 1
            assert any("process" in c.description for c in result_b.semantic_conflicts)

        await strategy.teardown_workspace(workspace=ws_a)
        await strategy.teardown_workspace(workspace=ws_b)

    async def test_semantic_disabled_returns_no_conflicts(
        self,
        tmp_path: Path,
    ) -> None:
        """When semantic analysis is disabled, no semantic conflicts reported."""
        repo = tmp_path / "repo"
        _init_test_repo(repo)

        _commit_file(
            repo,
            "utils.py",
            "def old_func():\n    pass\n",
            "Add utils",
        )

        strategy = _make_strategy(repo, semantic_enabled=False)

        ws = await strategy.setup_workspace(
            request=WorkspaceRequest(
                task_id="task-1",
                agent_id="agent-1",
            ),
        )
        _commit_file(
            Path(ws.worktree_path),
            "utils.py",
            "def new_func():\n    pass\n",
            "Rename function",
        )

        result = await strategy.merge_workspace(workspace=ws)
        assert result.success is True
        assert result.semantic_conflicts == ()

        await strategy.teardown_workspace(workspace=ws)
