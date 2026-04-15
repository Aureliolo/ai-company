"""Code applier.

Applies approved code modification proposals by writing files
to a git branch, running CI validation, and creating a draft PR
for human review.
"""

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING

from synthorg.meta.models import (
    ApplyResult,
    CodeOperation,
    ImprovementProposal,
    ProposalAltitude,
)
from synthorg.observability import get_logger
from synthorg.observability.events.meta import (
    META_APPLY_COMPLETED,
    META_APPLY_FAILED,
    META_CI_VALIDATION_FAILED,
    META_CODE_BRANCH_CREATED,
    META_CODE_FILE_WRITTEN,
    META_CODE_PR_CREATED,
)

if TYPE_CHECKING:
    from synthorg.meta.config import CodeModificationConfig
    from synthorg.meta.models import CodeChange
    from synthorg.meta.protocol import CIValidator

logger = get_logger(__name__)


class CodeApplier:
    """Applies code modification proposals.

    Creates a git branch, writes proposed file changes, runs CI
    validation, and creates a draft PR. Does NOT auto-merge --
    human review is mandatory.

    Args:
        ci_validator: CI validator for lint/type-check/test checks.
        code_modification_config: Code modification settings.
    """

    def __init__(
        self,
        *,
        ci_validator: CIValidator,
        code_modification_config: CodeModificationConfig,
    ) -> None:
        self._ci_validator = ci_validator
        self._config = code_modification_config

    @property
    def altitude(self) -> ProposalAltitude:
        """This applier handles code modification proposals."""
        return ProposalAltitude.CODE_MODIFICATION

    async def apply(
        self,
        proposal: ImprovementProposal,
    ) -> ApplyResult:
        """Apply code changes: branch, write, CI, commit, PR.

        Args:
            proposal: The approved code modification proposal.

        Returns:
            Result indicating success or failure.
        """
        project_root = Path.cwd()
        branch = f"{self._config.branch_prefix}/{str(proposal.id)[:8]}"
        try:
            return await self._apply_pipeline(
                proposal,
                branch,
                project_root,
            )
        except MemoryError, RecursionError:
            raise
        except Exception:
            logger.exception(
                META_APPLY_FAILED,
                altitude="code_modification",
                proposal_id=str(proposal.id),
            )
            try:
                await self._cleanup_branch(branch, project_root)
            except Exception:
                logger.exception(
                    META_APPLY_FAILED,
                    altitude="code_modification",
                    proposal_id=str(proposal.id),
                    reason="cleanup_failed",
                )
            return ApplyResult(
                success=False,
                error_message=("Code apply failed. Check logs for details."),
                changes_applied=0,
            )

    async def _apply_pipeline(
        self,
        proposal: ImprovementProposal,
        branch: str,
        project_root: Path,
    ) -> ApplyResult:
        """Execute the apply pipeline: branch, write, CI, commit, PR.

        Args:
            proposal: The approved proposal.
            branch: Git branch name.
            project_root: Absolute path to project root.

        Returns:
            Result indicating success or failure.
        """
        await self._run_git(
            "checkout",
            "-b",
            branch,
            cwd=project_root,
        )
        logger.info(
            META_CODE_BRANCH_CREATED,
            branch=branch,
            proposal_id=str(proposal.id),
        )

        changed_files = await self._write_changes(
            proposal.code_changes,
            project_root,
        )

        ci_result = await self._ci_validator.validate(
            project_root=project_root,
            changed_files=tuple(changed_files),
        )
        if not ci_result.passed:
            logger.warning(
                META_CI_VALIDATION_FAILED,
                proposal_id=str(proposal.id),
                errors=list(ci_result.errors),
            )
            await self._cleanup_branch(branch, project_root)
            return ApplyResult(
                success=False,
                error_message=(f"CI validation failed: {'; '.join(ci_result.errors)}"),
                changes_applied=0,
            )

        await self._commit_and_push(
            changed_files,
            proposal,
            branch,
            project_root,
        )
        pr_url = await self._create_pr(
            branch,
            proposal,
            project_root,
        )

        count = len(proposal.code_changes)
        logger.info(
            META_APPLY_COMPLETED,
            altitude="code_modification",
            changes=count,
            proposal_id=str(proposal.id),
            branch=branch,
            pr_url=pr_url,
        )
        return ApplyResult(success=True, changes_applied=count)

    async def _commit_and_push(
        self,
        changed_files: list[str],
        proposal: ImprovementProposal,
        branch: str,
        project_root: Path,
    ) -> None:
        """Stage, commit, and push changes.

        Args:
            changed_files: Relative paths of changed files.
            proposal: The proposal being applied.
            branch: Git branch name.
            project_root: Absolute path to project root.
        """
        await self._run_git(
            "add",
            *changed_files,
            cwd=project_root,
        )
        await self._run_git(
            "commit",
            "-m",
            f"feat: {proposal.title}\n\n"
            f"Auto-generated by meta-loop code modification.\n"
            f"Proposal: {proposal.id}",
            cwd=project_root,
        )
        await self._run_git(
            "push",
            "-u",
            "origin",
            branch,
            cwd=project_root,
        )

    async def dry_run(
        self,
        proposal: ImprovementProposal,
    ) -> ApplyResult:
        """Validate code changes without applying.

        Checks file path scope, operation consistency, and
        target file existence for modify/delete operations.

        Args:
            proposal: The proposal to validate.

        Returns:
            Result indicating whether apply would succeed.
        """
        project_root = Path.cwd()
        errors: list[str] = []

        for change in proposal.code_changes:
            file_path = project_root / change.file_path
            if change.operation == CodeOperation.MODIFY:
                if not file_path.exists():
                    errors.append(f"MODIFY target does not exist: {change.file_path}")
            elif change.operation == CodeOperation.DELETE:
                if not file_path.exists():
                    errors.append(f"DELETE target does not exist: {change.file_path}")
            elif change.operation == CodeOperation.CREATE and file_path.exists():
                errors.append(f"CREATE target already exists: {change.file_path}")

        if errors:
            return ApplyResult(
                success=False,
                error_message="; ".join(errors),
                changes_applied=0,
            )
        return ApplyResult(
            success=True,
            changes_applied=len(proposal.code_changes),
        )

    async def _write_changes(
        self,
        changes: tuple[CodeChange, ...],
        project_root: Path,
    ) -> list[str]:
        """Write code changes to disk.

        Args:
            changes: Code changes to apply.
            project_root: Absolute path to project root.

        Returns:
            List of relative file paths that were changed.
        """
        changed: list[str] = []
        for change in changes:
            file_path = project_root / change.file_path
            if change.operation == CodeOperation.CREATE:
                file_path.parent.mkdir(parents=True, exist_ok=True)
                file_path.write_text(
                    change.new_content,
                    encoding="utf-8",
                )
            elif change.operation == CodeOperation.MODIFY:
                file_path.write_text(
                    change.new_content,
                    encoding="utf-8",
                )
            elif change.operation == CodeOperation.DELETE:
                file_path.unlink(missing_ok=True)
            changed.append(change.file_path)
            logger.debug(
                META_CODE_FILE_WRITTEN,
                operation=change.operation.value,
                file_path=change.file_path,
            )
        return changed

    async def _create_pr(
        self,
        branch: str,
        proposal: ImprovementProposal,
        cwd: Path,
    ) -> str:
        """Create a draft PR via gh CLI.

        Args:
            branch: Branch name.
            proposal: The proposal being applied.
            cwd: Working directory.

        Returns:
            PR URL string.
        """
        proc = await asyncio.create_subprocess_exec(
            "gh",
            "pr",
            "create",
            "--draft",
            "--title",
            proposal.title,
            "--body",
            f"## Meta-Loop Code Modification\n\n"
            f"**Proposal ID**: {proposal.id}\n"
            f"**Source Rule**: {proposal.source_rule}\n"
            f"**Confidence**: {proposal.confidence:.0%}\n\n"
            f"### Rationale\n\n"
            f"{proposal.rationale.signal_summary}\n\n"
            f"### Changes\n\n"
            f"{proposal.description}\n\n"
            f"---\n"
            f"*Auto-generated by the self-improvement meta-loop. "
            f"Human review required before merge.*",
            "--head",
            branch,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await proc.communicate()
        except asyncio.CancelledError:
            proc.kill()
            await proc.wait()
            raise
        if proc.returncode != 0:
            stderr_text = stderr.decode(errors="replace").strip()
            msg = f"gh pr create failed: {stderr_text}"
            raise RuntimeError(msg)
        pr_url = stdout.decode().strip()
        logger.info(
            META_CODE_PR_CREATED,
            proposal_id=str(proposal.id),
            pr_url=pr_url,
        )
        return pr_url

    async def _run_git(
        self,
        *args: str,
        cwd: Path,
    ) -> None:
        """Run a git command.

        Args:
            *args: Git subcommand and arguments.
            cwd: Working directory.

        Raises:
            RuntimeError: If git command fails.
        """
        proc = await asyncio.create_subprocess_exec(
            "git",
            *args,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            _, stderr = await proc.communicate()
        except asyncio.CancelledError:
            proc.kill()
            await proc.wait()
            raise
        if proc.returncode != 0:
            msg = f"git {args[0]} failed: {stderr.decode(errors='replace').strip()}"
            raise RuntimeError(msg)

    async def _cleanup_branch(
        self,
        branch: str,
        cwd: Path,
    ) -> None:
        """Switch back to main and delete the branch.

        Args:
            branch: Branch name to delete.
            cwd: Working directory.
        """
        await self._run_git("checkout", "main", cwd=cwd)
        await self._run_git("branch", "-D", branch, cwd=cwd)
