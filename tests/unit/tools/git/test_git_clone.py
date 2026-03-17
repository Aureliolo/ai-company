"""Integration tests for GitCloneTool (clone + SSRF prevention)."""

from pathlib import Path

import pytest

from synthorg.tools.git_tools import GitCloneTool
from synthorg.tools.git_url_validator import GitCloneNetworkPolicy

from .conftest import _run_git

pytestmark = pytest.mark.timeout(30)


# ── GitCloneTool ──────────────────────────────────────────────────


@pytest.mark.unit
class TestGitCloneTool:
    """Tests for git_clone."""

    async def test_clone_local_repo(
        self,
        git_repo: Path,
        workspace: Path,
        allow_local_clone: None,
    ) -> None:
        tool = GitCloneTool(workspace=workspace)
        result = await tool.execute(
            arguments={
                "url": str(git_repo),
                "directory": "cloned",
            },
        )
        assert not result.is_error
        assert (workspace / "cloned" / "README.md").exists()

    async def test_clone_with_depth(
        self,
        git_repo: Path,
        workspace: Path,
        allow_local_clone: None,
    ) -> None:
        tool = GitCloneTool(workspace=workspace)
        result = await tool.execute(
            arguments={
                "url": str(git_repo),
                "directory": "shallow",
                "depth": 1,
            },
        )
        assert not result.is_error

    async def test_clone_directory_outside_workspace(
        self,
        git_repo: Path,
        workspace: Path,
        allow_local_clone: None,
    ) -> None:
        tool = GitCloneTool(workspace=workspace)
        result = await tool.execute(
            arguments={
                "url": str(git_repo),
                "directory": "../../outside",
            },
        )
        assert result.is_error

    async def test_clone_invalid_url(self, clone_tool: GitCloneTool) -> None:
        result = await clone_tool.execute(
            arguments={"url": "not-a-real-url-at-all"},
        )
        assert result.is_error
        assert "Invalid clone URL" in result.content

    async def test_clone_with_branch(
        self,
        git_repo: Path,
        workspace: Path,
        allow_local_clone: None,
    ) -> None:
        _run_git(["branch", "test-branch"], git_repo)
        tool = GitCloneTool(workspace=workspace)
        result = await tool.execute(
            arguments={
                "url": str(git_repo),
                "directory": "branch-clone",
                "branch": "test-branch",
            },
        )
        assert not result.is_error


# ── Security: SSRF prevention in clone ────────────────────────────


@pytest.mark.unit
class TestGitCloneToolSsrf:
    """SSRF prevention integration tests for git_clone."""

    async def test_clone_ssrf_loopback_blocked(
        self,
        workspace: Path,
    ) -> None:
        """Clone to loopback IP must be blocked."""
        tool = GitCloneTool(workspace=workspace)
        result = await tool.execute(
            arguments={"url": "https://127.0.0.1/repo.git"},
        )
        assert result.is_error
        assert "blocked" in result.content.lower()

    async def test_clone_ssrf_private_ip_blocked(
        self,
        workspace: Path,
    ) -> None:
        """Clone to private network IP must be blocked."""
        tool = GitCloneTool(workspace=workspace)
        result = await tool.execute(
            arguments={"url": "https://10.0.0.5/internal.git"},
        )
        assert result.is_error
        assert "blocked" in result.content.lower()

    async def test_clone_ssrf_allowlisted_host(
        self,
        workspace: Path,
    ) -> None:
        """Allowlisted host bypasses SSRF check."""
        policy = GitCloneNetworkPolicy(
            hostname_allowlist=("internal-git.example.com",),
        )
        tool = GitCloneTool(workspace=workspace, network_policy=policy)
        result = await tool.execute(
            arguments={
                "url": "https://internal-git.example.com/repo.git",
            },
        )
        # SSRF check passes (allowlisted); clone fails for other
        # reasons (host doesn't exist) — but NOT an SSRF error.
        assert "blocked" not in result.content.lower()
        assert "ssrf" not in result.content.lower()

    async def test_clone_file_scheme_blocked(
        self,
        clone_tool: GitCloneTool,
    ) -> None:
        """Scheme rejection wiring: file:// blocked end-to-end."""
        result = await clone_tool.execute(
            arguments={"url": "file:///etc"},
        )
        assert result.is_error
        assert "Invalid clone URL" in result.content
