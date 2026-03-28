"""Git operations for semantic conflict analysis.

Encapsulates the git plumbing (merge-base, diff, show) used by the
semantic analysis pipeline. Extracted from ``git_worktree.py`` to
keep the worktree strategy module under the 800-line budget.
"""

import asyncio
import re
from typing import TYPE_CHECKING

from synthorg.engine.workspace.semantic_analyzer import filter_files
from synthorg.observability import get_logger
from synthorg.observability.events.workspace import (
    WORKSPACE_SEMANTIC_ANALYSIS_FAILED,
    WORKSPACE_SEMANTIC_CONFLICT,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine

    from synthorg.engine.workspace.config import SemanticAnalysisConfig
    from synthorg.engine.workspace.models import MergeConflict, Workspace
    from synthorg.engine.workspace.semantic_analyzer import SemanticAnalyzer

    type GitRunner = Callable[..., Coroutine[object, object, tuple[int, str, str]]]

logger = get_logger(__name__)

_SAFE_FILE_PATH_RE = re.compile(r"^[A-Za-z0-9_./ @\-]+$")


def _validate_file_path(file_path: str) -> bool:
    """Return True if *file_path* is safe for use as a git path arg.

    Rejects empty strings, flag-like arguments, directory traversal,
    absolute paths, and characters outside a conservative allowlist.
    """
    if not file_path or file_path.startswith("-"):
        return False
    if ".." in file_path.split("/"):
        return False
    if file_path.startswith("/"):
        return False
    return bool(_SAFE_FILE_PATH_RE.match(file_path))


async def get_merge_base(
    run_git: GitRunner,
    sha_a: str,
    ref_b: str,
) -> str:
    """Find the merge base (common ancestor) of two refs.

    Args:
        run_git: Bound ``_run_git`` method from the strategy.
        sha_a: First ref (typically HEAD / main tip).
        ref_b: Second ref (typically workspace branch name).

    Returns:
        Merge base SHA, or empty string on failure.
    """
    rc, stdout, stderr = await run_git(
        "merge-base",
        sha_a,
        ref_b,
        log_event=WORKSPACE_SEMANTIC_ANALYSIS_FAILED,
    )
    if rc != 0:
        logger.warning(
            WORKSPACE_SEMANTIC_ANALYSIS_FAILED,
            operation="merge-base",
            sha_a=sha_a,
            ref_b=ref_b,
            error=stderr,
        )
        return ""
    return stdout.strip()


async def get_changed_files(
    run_git: GitRunner,
    base_sha: str,
    merge_sha: str,
) -> tuple[str, ...]:
    """Get files changed between two commits.

    Args:
        run_git: Bound ``_run_git`` method from the strategy.
        base_sha: Commit SHA to diff from.
        merge_sha: Commit SHA to diff to.

    Returns:
        Tuple of changed file paths (safe paths only).
    """
    rc, stdout, stderr = await run_git(
        "diff",
        "--name-only",
        f"{base_sha}..{merge_sha}",
        log_event=WORKSPACE_SEMANTIC_ANALYSIS_FAILED,
    )
    if rc != 0:
        logger.warning(
            WORKSPACE_SEMANTIC_ANALYSIS_FAILED,
            operation="diff",
            base_sha=base_sha,
            merge_sha=merge_sha,
            error=stderr,
        )
        return ()
    if not stdout:
        return ()
    return tuple(
        line.strip()
        for line in stdout.splitlines()
        if line.strip() and _validate_file_path(line.strip())
    )


async def get_base_sources(
    run_git: GitRunner,
    base_sha: str,
    files: tuple[str, ...],
    *,
    concurrency: int = 10,
) -> dict[str, str]:
    """Read file contents at a specific commit via parallel git show.

    Args:
        run_git: Bound ``_run_git`` method from the strategy.
        base_sha: Commit SHA to read from.
        files: File paths to read.
        concurrency: Maximum concurrent git show calls.

    Returns:
        Mapping of file path to content at the given commit.
    """
    sources: dict[str, str] = {}
    sem = asyncio.Semaphore(concurrency)

    async def _fetch(fp: str) -> None:
        async with sem:
            if not _validate_file_path(fp):
                logger.warning(
                    WORKSPACE_SEMANTIC_ANALYSIS_FAILED,
                    operation="show",
                    file=fp,
                    error="unsafe file path",
                )
                return
            rc, stdout, stderr = await run_git(
                "show",
                f"{base_sha}:{fp}",
                log_event=WORKSPACE_SEMANTIC_ANALYSIS_FAILED,
            )
            if rc == 0:
                sources[fp] = stdout
            else:
                logger.debug(
                    WORKSPACE_SEMANTIC_ANALYSIS_FAILED,
                    operation="show",
                    base_sha=base_sha,
                    file=fp,
                    error=stderr,
                )

    async with asyncio.TaskGroup() as tg:
        for file_path in files:
            tg.create_task(_fetch(file_path))
    return sources


async def run_semantic_analysis(  # noqa: PLR0913
    *,
    run_git: GitRunner,
    config: SemanticAnalysisConfig,
    analyzer: SemanticAnalyzer | None,
    repo_root: str,
    workspace: Workspace,
    pre_merge_sha: str,
    merge_sha: str,
) -> tuple[MergeConflict, ...]:
    """Run semantic analysis on a successful merge if configured.

    Orchestrates the full pipeline: finds merge base, gets changed
    files, fetches base sources, and invokes the analyzer. Returns
    ``()`` when disabled, not configured, or on failure.

    Args:
        run_git: Bound ``_run_git`` method from the strategy.
        config: Semantic analysis configuration.
        analyzer: Configured ``SemanticAnalyzer``, or ``None``.
        repo_root: Absolute path to the repository root.
        workspace: The merged workspace.
        pre_merge_sha: Main tip before the merge.
        merge_sha: Commit SHA after the merge.

    Returns:
        Tuple of semantic ``MergeConflict`` instances.
    """
    if analyzer is None or not pre_merge_sha:
        return ()
    if not config.enabled:
        return ()
    result = await _do_analysis(
        run_git=run_git,
        config=config,
        analyzer=analyzer,
        repo_root=repo_root,
        workspace=workspace,
        pre_merge_sha=pre_merge_sha,
        merge_sha=merge_sha,
    )
    if result:
        logger.warning(
            WORKSPACE_SEMANTIC_CONFLICT,
            workspace_id=workspace.workspace_id,
            count=len(result),
        )
    return result


async def _do_analysis(  # noqa: PLR0913
    *,
    run_git: GitRunner,
    config: SemanticAnalysisConfig,
    analyzer: SemanticAnalyzer,
    repo_root: str,
    workspace: Workspace,
    pre_merge_sha: str,
    merge_sha: str,
) -> tuple[MergeConflict, ...]:
    """Execute semantic analysis, returning ``()`` on failure."""
    try:
        branch_point = await get_merge_base(
            run_git,
            pre_merge_sha,
            workspace.branch_name,
        )
        if not branch_point:
            branch_point = pre_merge_sha

        changed_files = await get_changed_files(
            run_git,
            branch_point,
            merge_sha,
        )
        if not changed_files:
            return ()

        filtered = tuple(filter_files(changed_files, config))
        if not filtered:
            return ()

        base_sources = await get_base_sources(
            run_git,
            branch_point,
            filtered,
            concurrency=config.git_concurrency,
        )

        return await analyzer.analyze(
            workspace=workspace,
            changed_files=filtered,
            repo_root=repo_root,
            base_sources=base_sources,
        )
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        logger.warning(
            WORKSPACE_SEMANTIC_ANALYSIS_FAILED,
            workspace_id=workspace.workspace_id,
            error=f"Semantic analysis failed: {type(exc).__name__}: {exc}",
            exc_info=True,
        )
        return ()
