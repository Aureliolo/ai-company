"""Unit tests for code modification applier."""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from synthorg.meta.appliers.code_applier import CodeApplier
from synthorg.meta.config import CodeModificationConfig
from synthorg.meta.models import (
    CIValidationResult,
    CodeChange,
    CodeOperation,
    ImprovementProposal,
    ProposalAltitude,
    ProposalRationale,
    RollbackOperation,
    RollbackPlan,
)

pytestmark = pytest.mark.unit


def _rationale() -> ProposalRationale:
    return ProposalRationale(
        signal_summary="test",
        pattern_detected="test",
        expected_impact="test",
        confidence_reasoning="test",
    )


def _rollback() -> RollbackPlan:
    return RollbackPlan(
        operations=(
            RollbackOperation(
                operation_type="revert_branch",
                target="meta/code-mod/test",
                description="revert",
            ),
        ),
        validation_check="branch deleted",
    )


def _code_proposal(
    *,
    changes: tuple[CodeChange, ...] | None = None,
) -> ImprovementProposal:
    if changes is None:
        changes = (
            CodeChange(
                file_path="src/synthorg/meta/strategies/new.py",
                operation=CodeOperation.CREATE,
                new_content="class New:\n    pass\n",
                description="Add new strategy",
                reasoning="Quality declining",
            ),
        )
    return ImprovementProposal(
        altitude=ProposalAltitude.CODE_MODIFICATION,
        title="Test code proposal",
        description="Test description",
        rationale=_rationale(),
        code_changes=changes,
        rollback_plan=_rollback(),
        confidence=0.6,
        source_rule="quality_declining",
    )


def _ci_pass() -> CIValidationResult:
    return CIValidationResult(
        passed=True,
        lint_passed=True,
        typecheck_passed=True,
        tests_passed=True,
        duration_seconds=5.0,
    )


def _ci_fail() -> CIValidationResult:
    return CIValidationResult(
        passed=False,
        lint_passed=False,
        typecheck_passed=True,
        tests_passed=True,
        errors=("lint: E501 line too long",),
        duration_seconds=2.0,
    )


def _mock_ci_validator(
    result: CIValidationResult | None = None,
) -> AsyncMock:
    ci = AsyncMock()
    ci.validate = AsyncMock(return_value=result or _ci_pass())
    return ci


def _mock_github_client() -> AsyncMock:
    """Mock GitHubAPI that succeeds on all operations."""
    gh = AsyncMock()
    gh.create_branch = AsyncMock()
    gh.push_change = AsyncMock()
    gh.create_draft_pr = AsyncMock(
        return_value="https://github.com/test/repo/pull/99",
    )
    gh.delete_branch = AsyncMock()
    return gh


class TestCodeApplier:
    """Code applier tests."""

    def test_altitude(self) -> None:
        applier = CodeApplier(
            ci_validator=_mock_ci_validator(),
            github_client=_mock_github_client(),
            code_modification_config=CodeModificationConfig(),
        )
        assert applier.altitude == ProposalAltitude.CODE_MODIFICATION

    async def test_apply_success(self, tmp_path: Path) -> None:
        ci = _mock_ci_validator(_ci_pass())
        gh = _mock_github_client()
        applier = CodeApplier(
            ci_validator=ci,
            github_client=gh,
            code_modification_config=CodeModificationConfig(),
        )
        proposal = _code_proposal()

        with patch(
            "synthorg.meta.appliers.code_applier.Path.cwd",
            return_value=tmp_path,
        ):
            strategies_dir = tmp_path / "src" / "synthorg" / "meta" / "strategies"
            strategies_dir.mkdir(parents=True)
            result = await applier.apply(proposal)

        assert result.success
        assert result.changes_applied == 1
        # GitHub API was called.
        gh.create_branch.assert_awaited_once()
        gh.push_change.assert_awaited_once()
        gh.create_draft_pr.assert_awaited_once()
        # Local file was reverted after push.
        written = strategies_dir / "new.py"
        assert not written.exists()

    async def test_apply_ci_failure_reverts_local(
        self,
        tmp_path: Path,
    ) -> None:
        ci = _mock_ci_validator(_ci_fail())
        gh = _mock_github_client()
        applier = CodeApplier(
            ci_validator=ci,
            github_client=gh,
            code_modification_config=CodeModificationConfig(),
        )
        proposal = _code_proposal()

        with patch(
            "synthorg.meta.appliers.code_applier.Path.cwd",
            return_value=tmp_path,
        ):
            strategies_dir = tmp_path / "src" / "synthorg" / "meta" / "strategies"
            strategies_dir.mkdir(parents=True)
            result = await applier.apply(proposal)

        assert not result.success
        assert result.changes_applied == 0
        assert "CI validation failed" in (result.error_message or "")
        # GitHub API was NOT called (CI failed).
        gh.create_branch.assert_not_awaited()
        # Local file was reverted.
        written = strategies_dir / "new.py"
        assert not written.exists()

    async def test_apply_github_failure_cleans_up(
        self,
        tmp_path: Path,
    ) -> None:
        ci = _mock_ci_validator(_ci_pass())
        gh = _mock_github_client()
        gh.create_branch = AsyncMock(
            side_effect=RuntimeError("GitHub API failed"),
        )
        applier = CodeApplier(
            ci_validator=ci,
            github_client=gh,
            code_modification_config=CodeModificationConfig(),
        )
        proposal = _code_proposal()

        with patch(
            "synthorg.meta.appliers.code_applier.Path.cwd",
            return_value=tmp_path,
        ):
            strategies_dir = tmp_path / "src" / "synthorg" / "meta" / "strategies"
            strategies_dir.mkdir(parents=True)
            result = await applier.apply(proposal)

        assert not result.success
        assert "Code apply failed" in (result.error_message or "")
        # Cleanup was attempted.
        gh.delete_branch.assert_awaited_once()

    async def test_apply_pr_creation_failure(
        self,
        tmp_path: Path,
    ) -> None:
        ci = _mock_ci_validator(_ci_pass())
        gh = _mock_github_client()
        gh.create_draft_pr = AsyncMock(
            side_effect=RuntimeError("auth required"),
        )
        applier = CodeApplier(
            ci_validator=ci,
            github_client=gh,
            code_modification_config=CodeModificationConfig(),
        )
        proposal = _code_proposal()

        with patch(
            "synthorg.meta.appliers.code_applier.Path.cwd",
            return_value=tmp_path,
        ):
            strategies_dir = tmp_path / "src" / "synthorg" / "meta" / "strategies"
            strategies_dir.mkdir(parents=True)
            result = await applier.apply(proposal)

        assert not result.success
        assert "Code apply failed" in (result.error_message or "")

    async def test_dry_run_create_valid(self, tmp_path: Path) -> None:
        applier = CodeApplier(
            ci_validator=_mock_ci_validator(),
            github_client=_mock_github_client(),
            code_modification_config=CodeModificationConfig(),
        )
        proposal = _code_proposal()
        with patch(
            "synthorg.meta.appliers.code_applier.Path.cwd",
            return_value=tmp_path,
        ):
            result = await applier.dry_run(proposal)
        assert result.success
        assert result.changes_applied == 1

    async def test_dry_run_modify_missing_file(
        self,
        tmp_path: Path,
    ) -> None:
        changes = (
            CodeChange(
                file_path="src/synthorg/meta/strategies/missing.py",
                operation=CodeOperation.MODIFY,
                old_content="old",
                new_content="new",
                description="modify",
                reasoning="r",
            ),
        )
        applier = CodeApplier(
            ci_validator=_mock_ci_validator(),
            github_client=_mock_github_client(),
            code_modification_config=CodeModificationConfig(),
        )
        proposal = _code_proposal(changes=changes)
        with patch(
            "synthorg.meta.appliers.code_applier.Path.cwd",
            return_value=tmp_path,
        ):
            result = await applier.dry_run(proposal)
        assert not result.success
        assert "MODIFY target does not exist" in (result.error_message or "")

    async def test_dry_run_delete_missing_file(
        self,
        tmp_path: Path,
    ) -> None:
        changes = (
            CodeChange(
                file_path="src/synthorg/meta/strategies/gone.py",
                operation=CodeOperation.DELETE,
                old_content="old content",
                description="delete",
                reasoning="r",
            ),
        )
        applier = CodeApplier(
            ci_validator=_mock_ci_validator(),
            github_client=_mock_github_client(),
            code_modification_config=CodeModificationConfig(),
        )
        proposal = _code_proposal(changes=changes)
        with patch(
            "synthorg.meta.appliers.code_applier.Path.cwd",
            return_value=tmp_path,
        ):
            result = await applier.dry_run(proposal)
        assert not result.success
        assert "DELETE target does not exist" in (result.error_message or "")

    async def test_dry_run_create_already_exists(
        self,
        tmp_path: Path,
    ) -> None:
        target = tmp_path / "src" / "synthorg" / "meta" / "strategies"
        target.mkdir(parents=True)
        (target / "new.py").write_text("existing")
        applier = CodeApplier(
            ci_validator=_mock_ci_validator(),
            github_client=_mock_github_client(),
            code_modification_config=CodeModificationConfig(),
        )
        proposal = _code_proposal()
        with patch(
            "synthorg.meta.appliers.code_applier.Path.cwd",
            return_value=tmp_path,
        ):
            result = await applier.dry_run(proposal)
        assert not result.success
        assert "CREATE target already exists" in (result.error_message or "")
