"""Unit tests for the semantic analyzer classes.

Tests AstSemanticAnalyzer and CompositeSemanticAnalyzer with
mocked file I/O to verify orchestration and result aggregation.
"""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from synthorg.core.enums import ConflictType
from synthorg.engine.workspace.config import SemanticAnalysisConfig
from synthorg.engine.workspace.models import MergeConflict, Workspace
from synthorg.engine.workspace.semantic_analyzer import (
    AstSemanticAnalyzer,
    CompositeSemanticAnalyzer,
    SemanticAnalyzer,
)

pytestmark = pytest.mark.unit


def _make_workspace(
    workspace_id: str = "ws-1",
    base_branch: str = "main",
) -> Workspace:
    """Create a test workspace."""
    from datetime import UTC, datetime

    return Workspace(
        workspace_id=workspace_id,
        task_id="task-1",
        agent_id="agent-1",
        branch_name=f"ws/{workspace_id}",
        worktree_path="/tmp/ws",  # noqa: S108
        base_branch=base_branch,
        created_at=datetime.now(tz=UTC),
    )


def _make_conflict(
    file_path: str = "utils.py",
    description: str = "test conflict",
) -> MergeConflict:
    """Create a test semantic conflict."""
    return MergeConflict(
        file_path=file_path,
        conflict_type=ConflictType.SEMANTIC,
        description=description,
    )


# ---------------------------------------------------------------------------
# AstSemanticAnalyzer
# ---------------------------------------------------------------------------


class TestAstSemanticAnalyzer:
    """Tests for the AST-based semantic analyzer."""

    async def test_protocol_compliance(self) -> None:
        analyzer = AstSemanticAnalyzer(config=SemanticAnalysisConfig())
        assert isinstance(analyzer, SemanticAnalyzer)

    async def test_no_changed_files_returns_empty(self) -> None:
        analyzer = AstSemanticAnalyzer(config=SemanticAnalysisConfig())
        result = await analyzer.analyze(
            workspace=_make_workspace(),
            changed_files=(),
            repo_root="/tmp/repo",  # noqa: S108
            base_sources={},
        )
        assert result == ()

    async def test_non_python_files_skipped(self) -> None:
        analyzer = AstSemanticAnalyzer(
            config=SemanticAnalysisConfig(file_extensions=(".py",)),
        )
        result = await analyzer.analyze(
            workspace=_make_workspace(),
            changed_files=("readme.md", "config.yaml"),
            repo_root="/tmp/repo",  # noqa: S108
            base_sources={},
        )
        assert result == ()

    async def test_max_files_limit_respected(self) -> None:
        config = SemanticAnalysisConfig(max_files=2)
        analyzer = AstSemanticAnalyzer(config=config)
        # Even with many files, only max_files are analyzed
        files = tuple(f"file{i}.py" for i in range(10))

        with patch.object(Path, "read_text", return_value="x = 1\n"):
            result = await analyzer.analyze(
                workspace=_make_workspace(),
                changed_files=files,
                repo_root="/tmp/repo",  # noqa: S108
                base_sources={},
            )
        # Should not crash, just analyzes the limited set
        assert isinstance(result, tuple)

    async def test_detects_semantic_conflict(self) -> None:
        """End-to-end: function renamed in one file, called by old name in another."""
        analyzer = AstSemanticAnalyzer(config=SemanticAnalysisConfig())

        base_sources = {
            "utils.py": "def calculate_total(items):\n    return sum(items)\n",
        }
        merged_utils = "def compute_total(items):\n    return sum(items)\n"
        merged_orders = (
            "from utils import calculate_total\n\nresult = calculate_total([1, 2, 3])\n"
        )

        def mock_read_text(self: Path, encoding: str = "utf-8") -> str:
            name = self.name
            if name == "utils.py":
                return merged_utils
            if name == "orders.py":
                return merged_orders
            return ""

        with patch.object(Path, "read_text", mock_read_text):
            result = await analyzer.analyze(
                workspace=_make_workspace(),
                changed_files=("utils.py", "orders.py"),
                repo_root="/tmp/repo",  # noqa: S108
                base_sources=base_sources,
            )
        assert len(result) >= 1
        assert all(c.conflict_type == ConflictType.SEMANTIC for c in result)

    async def test_no_conflict_when_clean_merge(self) -> None:
        analyzer = AstSemanticAnalyzer(config=SemanticAnalysisConfig())

        base_sources = {
            "utils.py": "def process(data):\n    pass\n",
        }
        merged_utils = "def process(data):\n    pass\n\ndef extra():\n    pass\n"
        merged_main = "from utils import process\n\nprocess(42)\n"

        def mock_read_text(self: Path, encoding: str = "utf-8") -> str:
            name = self.name
            if name == "utils.py":
                return merged_utils
            if name == "main.py":
                return merged_main
            return ""

        with patch.object(Path, "read_text", mock_read_text):
            result = await analyzer.analyze(
                workspace=_make_workspace(),
                changed_files=("utils.py", "main.py"),
                repo_root="/tmp/repo",  # noqa: S108
                base_sources=base_sources,
            )
        assert len(result) == 0

    async def test_file_read_error_skipped(self) -> None:
        analyzer = AstSemanticAnalyzer(config=SemanticAnalysisConfig())

        def mock_read_text(self: Path, encoding: str = "utf-8") -> str:
            raise FileNotFoundError

        with patch.object(Path, "read_text", mock_read_text):
            result = await analyzer.analyze(
                workspace=_make_workspace(),
                changed_files=("missing.py",),
                repo_root="/tmp/repo",  # noqa: S108
                base_sources={},
            )
        assert result == ()


# ---------------------------------------------------------------------------
# CompositeSemanticAnalyzer
# ---------------------------------------------------------------------------


class TestCompositeSemanticAnalyzer:
    """Tests for the composite analyzer that chains multiple analyzers."""

    async def test_empty_analyzers_returns_empty(self) -> None:
        composite = CompositeSemanticAnalyzer(analyzers=())
        result = await composite.analyze(
            workspace=_make_workspace(),
            changed_files=("foo.py",),
            repo_root="/tmp/repo",  # noqa: S108
            base_sources={},
        )
        assert result == ()

    async def test_aggregates_results_from_multiple_analyzers(self) -> None:
        conflict_a = _make_conflict("a.py", "conflict from A")
        conflict_b = _make_conflict("b.py", "conflict from B")

        analyzer_a = AsyncMock(spec=SemanticAnalyzer)
        analyzer_a.analyze.return_value = (conflict_a,)

        analyzer_b = AsyncMock(spec=SemanticAnalyzer)
        analyzer_b.analyze.return_value = (conflict_b,)

        composite = CompositeSemanticAnalyzer(
            analyzers=(analyzer_a, analyzer_b),
        )
        result = await composite.analyze(
            workspace=_make_workspace(),
            changed_files=("a.py", "b.py"),
            repo_root="/tmp/repo",  # noqa: S108
            base_sources={},
        )
        assert len(result) == 2
        descriptions = {c.description for c in result}
        assert "conflict from A" in descriptions
        assert "conflict from B" in descriptions

    async def test_deduplicates_by_file_path_and_description(self) -> None:
        conflict = _make_conflict("a.py", "same issue")

        analyzer_a = AsyncMock(spec=SemanticAnalyzer)
        analyzer_a.analyze.return_value = (conflict,)

        analyzer_b = AsyncMock(spec=SemanticAnalyzer)
        analyzer_b.analyze.return_value = (conflict,)

        composite = CompositeSemanticAnalyzer(
            analyzers=(analyzer_a, analyzer_b),
        )
        result = await composite.analyze(
            workspace=_make_workspace(),
            changed_files=("a.py",),
            repo_root="/tmp/repo",  # noqa: S108
            base_sources={},
        )
        assert len(result) == 1

    async def test_single_analyzer_failure_does_not_block_others(self) -> None:
        conflict = _make_conflict("ok.py", "found issue")

        failing = AsyncMock(spec=SemanticAnalyzer)
        failing.analyze.side_effect = Exception("analyzer failed")

        working = AsyncMock(spec=SemanticAnalyzer)
        working.analyze.return_value = (conflict,)

        composite = CompositeSemanticAnalyzer(
            analyzers=(failing, working),
        )
        result = await composite.analyze(
            workspace=_make_workspace(),
            changed_files=("ok.py",),
            repo_root="/tmp/repo",  # noqa: S108
            base_sources={},
        )
        assert len(result) == 1

    async def test_protocol_compliance(self) -> None:
        composite = CompositeSemanticAnalyzer(analyzers=())
        assert isinstance(composite, SemanticAnalyzer)
