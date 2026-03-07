"""Integration tests for subprocess sandbox with real git."""

import os
import subprocess
from pathlib import Path  # noqa: TC003 — used at runtime

import pytest

from ai_company.tools.git_tools import GitStatusTool
from ai_company.tools.sandbox.config import SubprocessSandboxConfig
from ai_company.tools.sandbox.errors import SandboxError
from ai_company.tools.sandbox.subprocess_sandbox import SubprocessSandbox

pytestmark = [pytest.mark.integration, pytest.mark.timeout(30)]

_GIT_ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME": "Test",
    "GIT_AUTHOR_EMAIL": "test@test.local",
    "GIT_COMMITTER_NAME": "Test",
    "GIT_COMMITTER_EMAIL": "test@test.local",
    "GIT_TERMINAL_PROMPT": "0",
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_PROTOCOL_FROM_USER": "0",
}


def _init_repo(path: Path) -> None:
    """Initialize a git repo with one commit."""
    for args in (
        ["init"],
        ["config", "user.name", "Test"],
        ["config", "user.email", "test@test.local"],
    ):
        subprocess.run(  # noqa: S603
            ["git", *args],  # noqa: S607
            cwd=path,
            check=True,
            capture_output=True,
            env=_GIT_ENV,
        )
    (path / "README.md").write_text("# Test\n")
    subprocess.run(
        ["git", "add", "."],  # noqa: S607
        cwd=path,
        check=True,
        capture_output=True,
        env=_GIT_ENV,
    )
    subprocess.run(
        ["git", "commit", "-m", "initial"],  # noqa: S607
        cwd=path,
        check=True,
        capture_output=True,
        env=_GIT_ENV,
    )


class TestRealGitWithSandbox:
    """Real git repo + SubprocessSandbox + GitStatusTool."""

    async def test_git_status_via_sandbox(self, tmp_path: Path) -> None:
        _init_repo(tmp_path)
        sandbox = SubprocessSandbox(workspace=tmp_path)
        tool = GitStatusTool(workspace=tmp_path, sandbox=sandbox)
        result = await tool.execute(arguments={})
        assert not result.is_error

    async def test_git_status_porcelain_via_sandbox(
        self,
        tmp_path: Path,
    ) -> None:
        _init_repo(tmp_path)
        (tmp_path / "new.txt").write_text("new file")
        sandbox = SubprocessSandbox(workspace=tmp_path)
        tool = GitStatusTool(workspace=tmp_path, sandbox=sandbox)
        result = await tool.execute(arguments={"porcelain": True})
        assert not result.is_error
        assert "new.txt" in result.content


class TestSandboxWorkspaceEscape:
    """Sandbox blocks workspace escape in real subprocess."""

    async def test_cwd_escape_blocked(self, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        outside = tmp_path / "outside"
        outside.mkdir()
        sandbox = SubprocessSandbox(workspace=workspace)
        with pytest.raises(SandboxError, match="outside workspace"):
            await sandbox.execute(
                command="echo",
                args=("test",),
                cwd=outside,
            )


class TestSandboxTimeout:
    """Sandbox timeout on slow command."""

    async def test_timeout_on_slow_command(self, tmp_path: Path) -> None:
        sandbox = SubprocessSandbox(
            workspace=tmp_path,
            config=SubprocessSandboxConfig(timeout_seconds=1.0),
        )
        if os.name == "nt":
            result = await sandbox.execute(
                command="cmd",
                args=("/c", "ping", "-n", "10", "127.0.0.1"),
                timeout=0.5,
            )
        else:
            result = await sandbox.execute(
                command="sleep",
                args=("10",),
                timeout=0.5,
            )
        assert result.timed_out
        assert not result.success
