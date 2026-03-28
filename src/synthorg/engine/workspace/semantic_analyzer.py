"""Semantic conflict detection for workspace merges.

Analyzes merged code for logical inconsistencies that git's textual
merge cannot detect: removed-name references, signature mismatches,
duplicate definitions, and import conflicts.
"""

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from synthorg.engine.workspace.semantic_checks import (
    check_duplicate_definitions,
    check_import_conflicts,
    check_removed_references,
    check_signature_changes,
)
from synthorg.observability import get_logger
from synthorg.observability.events.workspace import (
    WORKSPACE_SEMANTIC_ANALYSIS_COMPLETE,
    WORKSPACE_SEMANTIC_ANALYSIS_FAILED,
    WORKSPACE_SEMANTIC_ANALYSIS_START,
    WORKSPACE_SEMANTIC_CONFLICT,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from synthorg.engine.workspace.config import SemanticAnalysisConfig
    from synthorg.engine.workspace.models import MergeConflict, Workspace

logger = get_logger(__name__)


@runtime_checkable
class SemanticAnalyzer(Protocol):
    """Protocol for semantic conflict analyzers.

    Implementations inspect merged files to detect logical conflicts
    that survived textual merge.
    """

    async def analyze(
        self,
        *,
        workspace: Workspace,
        changed_files: tuple[str, ...],
        repo_root: str,
        base_sources: Mapping[str, str],
    ) -> tuple[MergeConflict, ...]:
        """Analyze merged files for semantic conflicts.

        Args:
            workspace: The workspace that was just merged.
            changed_files: Paths of files modified by the merge.
            repo_root: Absolute path to the repository root.
            base_sources: Mapping of file path to source content
                before the merge.

        Returns:
            Tuple of semantic MergeConflict instances.
        """
        ...


def filter_files(
    changed_files: tuple[str, ...],
    config: SemanticAnalysisConfig,
) -> list[str]:
    """Filter changed files by extension and limit to max_files."""
    py_files = [
        f
        for f in changed_files
        if any(f.endswith(ext) for ext in config.file_extensions)
    ]
    return py_files[: config.max_files]


def _read_sources(
    root: Path,
    files: list[str],
    workspace_id: str,
) -> dict[str, str]:
    """Read file contents, skipping unreadable files with logging."""
    resolved_root = root.resolve()
    sources: dict[str, str] = {}
    for file_path in files:
        try:
            target = (root / file_path).resolve()
            if not target.is_relative_to(resolved_root):
                logger.warning(
                    WORKSPACE_SEMANTIC_ANALYSIS_FAILED,
                    workspace_id=workspace_id,
                    file=file_path,
                    reason="path_traversal",
                )
                continue
            sources[file_path] = target.read_text(encoding="utf-8")
        except OSError as exc:
            logger.debug(
                WORKSPACE_SEMANTIC_ANALYSIS_FAILED,
                workspace_id=workspace_id,
                file=file_path,
                reason="read_error",
                error=f"{type(exc).__name__}: {exc}",
            )
    return sources


def _run_ast_checks(
    base_sources: Mapping[str, str],
    merged_sources: dict[str, str],
) -> tuple[MergeConflict, ...]:
    """Run all AST semantic checks and return combined results."""
    all_conflicts: list[MergeConflict] = []
    all_conflicts.extend(
        check_removed_references(
            base_sources=base_sources,
            merged_sources=merged_sources,
        ),
    )
    all_conflicts.extend(
        check_signature_changes(
            base_sources=base_sources,
            merged_sources=merged_sources,
        ),
    )
    all_conflicts.extend(
        check_duplicate_definitions(merged_sources=merged_sources),
    )
    all_conflicts.extend(
        check_import_conflicts(
            base_sources=base_sources,
            merged_sources=merged_sources,
        ),
    )
    return tuple(all_conflicts)


class AstSemanticAnalyzer:
    """Deterministic AST-based semantic conflict analyzer.

    Reads merged Python files and runs structural checks to detect
    removed-name references, signature mismatches, duplicate
    definitions, and import conflicts.

    Args:
        config: Semantic analysis configuration.
    """

    __slots__ = ("_config",)

    def __init__(self, *, config: SemanticAnalysisConfig) -> None:
        self._config = config

    async def analyze(
        self,
        *,
        workspace: Workspace,
        changed_files: tuple[str, ...],
        repo_root: str,
        base_sources: Mapping[str, str],
    ) -> tuple[MergeConflict, ...]:
        """Analyze merged Python files for semantic conflicts.

        Args:
            workspace: The workspace that was just merged.
            changed_files: Paths of files modified by the merge.
            repo_root: Absolute path to the repository root.
            base_sources: Mapping of file path to source content
                before the merge.

        Returns:
            Tuple of semantic MergeConflict instances.
        """
        py_files = filter_files(changed_files, self._config)
        logger.info(
            WORKSPACE_SEMANTIC_ANALYSIS_START,
            workspace_id=workspace.workspace_id,
            file_count=len(py_files),
        )
        if not py_files:
            return self._log_complete(workspace.workspace_id, 0, 0)

        merged_sources = await asyncio.to_thread(
            _read_sources,
            Path(repo_root),
            py_files,
            workspace.workspace_id,
        )
        if not merged_sources:
            return self._log_complete(workspace.workspace_id, 0, 0)

        result = _run_ast_checks(base_sources, merged_sources)

        if result:
            logger.warning(
                WORKSPACE_SEMANTIC_CONFLICT,
                workspace_id=workspace.workspace_id,
                count=len(result),
            )
        return self._log_complete(
            workspace.workspace_id,
            len(merged_sources),
            len(result),
            conflicts=result,
        )

    @staticmethod
    def _log_complete(
        workspace_id: str,
        analyzed: int,
        count: int,
        *,
        conflicts: tuple[MergeConflict, ...] = (),
    ) -> tuple[MergeConflict, ...]:
        """Log completion and return conflicts."""
        logger.info(
            WORKSPACE_SEMANTIC_ANALYSIS_COMPLETE,
            workspace_id=workspace_id,
            analyzed=analyzed,
            conflicts=count,
        )
        return conflicts


class CompositeSemanticAnalyzer:
    """Chains multiple semantic analyzers and deduplicates results.

    Runs each analyzer in order and collects all conflicts. If an
    analyzer raises an exception, it is logged and skipped.

    Args:
        analyzers: Ordered tuple of analyzers to run.
    """

    __slots__ = ("_analyzers",)

    def __init__(
        self,
        *,
        analyzers: tuple[SemanticAnalyzer, ...],
    ) -> None:
        self._analyzers = analyzers

    async def analyze(
        self,
        *,
        workspace: Workspace,
        changed_files: tuple[str, ...],
        repo_root: str,
        base_sources: Mapping[str, str],
    ) -> tuple[MergeConflict, ...]:
        """Run all analyzers and return deduplicated results.

        Args:
            workspace: The workspace that was just merged.
            changed_files: Paths of files modified by the merge.
            repo_root: Absolute path to the repository root.
            base_sources: Mapping of file path to source content
                before the merge.

        Returns:
            Deduplicated tuple of semantic conflicts from all analyzers.
        """
        all_conflicts: list[MergeConflict] = []

        async def _run(analyzer: SemanticAnalyzer) -> None:
            try:
                conflicts = await analyzer.analyze(
                    workspace=workspace,
                    changed_files=changed_files,
                    repo_root=repo_root,
                    base_sources=base_sources,
                )
                all_conflicts.extend(conflicts)
            except Exception as exc:
                logger.warning(
                    WORKSPACE_SEMANTIC_ANALYSIS_FAILED,
                    workspace_id=workspace.workspace_id,
                    analyzer=type(analyzer).__name__,
                    reason="analyzer_error",
                    error=f"{type(exc).__name__}: {exc}",
                    exc_info=True,
                )

        async with asyncio.TaskGroup() as tg:
            for analyzer in self._analyzers:
                tg.create_task(_run(analyzer))

        # Deduplicate by (file_path, description)
        seen: set[tuple[str, str]] = set()
        unique: list[MergeConflict] = []
        for conflict in all_conflicts:
            key = (conflict.file_path, conflict.description)
            if key not in seen:
                seen.add(key)
                unique.append(conflict)

        return tuple(unique)
