"""Planner-worktrees workspace isolation strategy.

Uses git worktrees to provide each agent with an isolated working
directory backed by its own branch.
"""

import asyncio
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from ai_company.engine.errors import (
    WorkspaceCleanupError,
    WorkspaceLimitError,
    WorkspaceMergeError,
    WorkspaceSetupError,
)
from ai_company.engine.workspace.config import PlannerWorktreesConfig  # noqa: TC001
from ai_company.engine.workspace.models import (
    MergeConflict,
    MergeResult,
    Workspace,
    WorkspaceRequest,
)
from ai_company.observability import get_logger
from ai_company.observability.events.workspace import (
    WORKSPACE_LIMIT_REACHED,
    WORKSPACE_MERGE_COMPLETE,
    WORKSPACE_MERGE_CONFLICT,
    WORKSPACE_MERGE_FAILED,
    WORKSPACE_MERGE_START,
    WORKSPACE_SETUP_COMPLETE,
    WORKSPACE_SETUP_FAILED,
    WORKSPACE_SETUP_START,
    WORKSPACE_TEARDOWN_COMPLETE,
    WORKSPACE_TEARDOWN_FAILED,
    WORKSPACE_TEARDOWN_START,
)

logger = get_logger(__name__)


class PlannerWorktreeStrategy:
    """Git-worktree-based workspace isolation strategy.

    Creates a separate git worktree and branch for each agent task,
    allowing concurrent work without interference.

    Args:
        config: Planner worktrees configuration.
        repo_root: Path to the main repository root.
    """

    __slots__ = (
        "_active_workspaces",
        "_config",
        "_lock",
        "_repo_root",
    )

    def __init__(
        self,
        *,
        config: PlannerWorktreesConfig,
        repo_root: Path,
    ) -> None:
        self._config = config
        self._repo_root = repo_root
        self._active_workspaces: dict[str, Workspace] = {}
        self._lock = asyncio.Lock()

    async def _run_git(
        self,
        *args: str,
    ) -> tuple[int, str, str]:
        """Run a git command in the repository root.

        Args:
            *args: Git command arguments.

        Returns:
            Tuple of (return_code, stdout, stderr).
        """
        proc = await asyncio.create_subprocess_exec(
            "git",
            *args,
            cwd=str(self._repo_root),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout_bytes, stderr_bytes = await proc.communicate()
        return (
            proc.returncode or 0,
            stdout_bytes.decode().strip(),
            stderr_bytes.decode().strip(),
        )

    async def setup_workspace(
        self,
        *,
        request: WorkspaceRequest,
    ) -> Workspace:
        """Create an isolated workspace via git worktree.

        Args:
            request: Workspace creation request.

        Returns:
            The created workspace.

        Raises:
            WorkspaceLimitError: When max concurrent worktrees reached.
            WorkspaceSetupError: When git operations fail.
        """
        async with self._lock:
            if len(self._active_workspaces) >= self._config.max_concurrent_worktrees:
                logger.warning(
                    WORKSPACE_LIMIT_REACHED,
                    current=len(self._active_workspaces),
                    limit=self._config.max_concurrent_worktrees,
                )
                msg = (
                    f"Maximum concurrent worktrees "
                    f"({self._config.max_concurrent_worktrees}) "
                    f"reached"
                )
                raise WorkspaceLimitError(msg)

            workspace_id = str(uuid4())
            branch_name = f"workspace/{request.task_id}"
            worktree_dir = self._resolve_worktree_path(workspace_id)

            logger.info(
                WORKSPACE_SETUP_START,
                workspace_id=workspace_id,
                task_id=request.task_id,
                agent_id=request.agent_id,
            )

            # Create branch from base
            rc, _, stderr = await self._run_git(
                "branch",
                branch_name,
                request.base_branch,
            )
            if rc != 0:
                logger.warning(
                    WORKSPACE_SETUP_FAILED,
                    workspace_id=workspace_id,
                    error=stderr,
                )
                msg = f"Failed to create branch '{branch_name}': {stderr}"
                raise WorkspaceSetupError(msg)

            # Create worktree
            rc, _, stderr = await self._run_git(
                "worktree",
                "add",
                str(worktree_dir),
                branch_name,
            )
            if rc != 0:
                logger.warning(
                    WORKSPACE_SETUP_FAILED,
                    workspace_id=workspace_id,
                    error=stderr,
                )
                msg = f"Failed to create worktree at '{worktree_dir}': {stderr}"
                raise WorkspaceSetupError(msg)

            workspace = Workspace(
                workspace_id=workspace_id,
                task_id=request.task_id,
                agent_id=request.agent_id,
                branch_name=branch_name,
                worktree_path=str(worktree_dir),
                base_branch=request.base_branch,
                created_at=datetime.now(UTC).isoformat(),
            )
            self._active_workspaces[workspace_id] = workspace

            logger.info(
                WORKSPACE_SETUP_COMPLETE,
                workspace_id=workspace_id,
                branch_name=branch_name,
            )
            return workspace

    async def merge_workspace(
        self,
        *,
        workspace: Workspace,
    ) -> MergeResult:
        """Merge workspace branch into base branch.

        Args:
            workspace: The workspace to merge.

        Returns:
            Merge result with conflict details if any.

        Raises:
            WorkspaceMergeError: When checkout of base branch fails.
        """
        start = time.monotonic()
        logger.info(
            WORKSPACE_MERGE_START,
            workspace_id=workspace.workspace_id,
            branch_name=workspace.branch_name,
        )

        # Checkout base branch in main repo
        rc, _, stderr = await self._run_git(
            "checkout",
            workspace.base_branch,
        )
        if rc != 0:
            logger.warning(
                WORKSPACE_MERGE_FAILED,
                workspace_id=workspace.workspace_id,
                error=stderr,
            )
            msg = f"Failed to checkout '{workspace.base_branch}': {stderr}"
            raise WorkspaceMergeError(msg)

        # Attempt merge
        rc, _, stderr = await self._run_git(
            "merge",
            "--no-ff",
            workspace.branch_name,
        )
        elapsed = time.monotonic() - start

        if rc == 0:
            # Get merge commit SHA
            _, sha_out, _ = await self._run_git("rev-parse", "HEAD")
            logger.info(
                WORKSPACE_MERGE_COMPLETE,
                workspace_id=workspace.workspace_id,
                commit_sha=sha_out,
            )
            return MergeResult(
                workspace_id=workspace.workspace_id,
                branch_name=workspace.branch_name,
                success=True,
                merged_commit_sha=sha_out,
                duration_seconds=elapsed,
            )

        # Conflict detected — collect conflicting files
        logger.warning(
            WORKSPACE_MERGE_CONFLICT,
            workspace_id=workspace.workspace_id,
            error=stderr,
        )
        conflicts = await self._collect_conflicts()

        # Abort the failed merge
        await self._run_git("merge", "--abort")

        return MergeResult(
            workspace_id=workspace.workspace_id,
            branch_name=workspace.branch_name,
            success=False,
            conflicts=conflicts,
            duration_seconds=time.monotonic() - start,
        )

    async def teardown_workspace(
        self,
        *,
        workspace: Workspace,
    ) -> None:
        """Remove worktree and branch, unregister workspace.

        Args:
            workspace: The workspace to tear down.

        Raises:
            WorkspaceCleanupError: When git operations fail.
        """
        logger.info(
            WORKSPACE_TEARDOWN_START,
            workspace_id=workspace.workspace_id,
        )

        # Remove worktree
        rc, _, stderr = await self._run_git(
            "worktree",
            "remove",
            workspace.worktree_path,
            "--force",
        )
        if rc != 0:
            logger.warning(
                WORKSPACE_TEARDOWN_FAILED,
                workspace_id=workspace.workspace_id,
                error=stderr,
            )
            msg = f"Failed to remove worktree '{workspace.worktree_path}': {stderr}"
            raise WorkspaceCleanupError(msg)

        # Delete branch (force: branch may not be fully merged)
        rc, _, stderr = await self._run_git(
            "branch",
            "-D",
            workspace.branch_name,
        )
        if rc != 0:
            logger.warning(
                WORKSPACE_TEARDOWN_FAILED,
                workspace_id=workspace.workspace_id,
                error=stderr,
            )
            msg = f"Failed to delete branch '{workspace.branch_name}': {stderr}"
            raise WorkspaceCleanupError(msg)

        self._active_workspaces.pop(workspace.workspace_id, None)
        logger.info(
            WORKSPACE_TEARDOWN_COMPLETE,
            workspace_id=workspace.workspace_id,
        )

    async def list_active_workspaces(self) -> tuple[Workspace, ...]:
        """Return all currently active workspaces.

        Returns:
            Tuple of active workspaces.
        """
        return tuple(self._active_workspaces.values())

    def get_strategy_type(self) -> str:
        """Return the strategy type identifier.

        Returns:
            Strategy type name.
        """
        return "planner_worktrees"

    def _resolve_worktree_path(self, workspace_id: str) -> Path:
        """Resolve the filesystem path for a new worktree.

        Args:
            workspace_id: Unique workspace identifier.

        Returns:
            Path where the worktree will be created.
        """
        if self._config.worktree_base_dir:
            base = Path(self._config.worktree_base_dir)
        else:
            base = self._repo_root.parent / ".worktrees"
        return base / workspace_id

    async def _collect_conflicts(self) -> tuple[MergeConflict, ...]:
        """Collect conflicting file paths after a failed merge.

        Returns:
            Tuple of MergeConflict instances for each conflict.
        """
        rc, stdout, _ = await self._run_git(
            "diff",
            "--name-only",
            "--diff-filter=U",
        )
        if rc != 0 or not stdout:
            return ()

        conflicts: list[MergeConflict] = []
        for line in stdout.splitlines():
            file_path = line.strip()
            if file_path:
                conflicts.append(
                    MergeConflict(
                        file_path=file_path,
                        conflict_type="textual",
                    ),
                )
        return tuple(conflicts)
