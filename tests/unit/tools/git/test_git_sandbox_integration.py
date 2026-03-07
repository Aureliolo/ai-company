"""Tests for git tools with sandbox integration."""

import os
import subprocess
from pathlib import Path  # noqa: TC003 — used at runtime
from unittest.mock import AsyncMock

import pytest

from ai_company.tools.git_tools import GitLogTool, GitStatusTool
from ai_company.tools.sandbox.errors import SandboxError
from ai_company.tools.sandbox.result import SandboxResult
from ai_company.tools.sandbox.subprocess_sandbox import SubprocessSandbox

pytestmark = [pytest.mark.unit, pytest.mark.timeout(30)]

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


class TestGitToolsWithSandbox:
    """Git tools work when a sandbox is injected."""

    async def test_status_with_sandbox(self, tmp_path: Path) -> None:
        _init_repo(tmp_path)
        sandbox = SubprocessSandbox(workspace=tmp_path)
        tool = GitStatusTool(workspace=tmp_path, sandbox=sandbox)
        result = await tool.execute(arguments={})
        assert not result.is_error

    async def test_log_with_sandbox(self, tmp_path: Path) -> None:
        _init_repo(tmp_path)
        sandbox = SubprocessSandbox(workspace=tmp_path)
        tool = GitLogTool(workspace=tmp_path, sandbox=sandbox)
        result = await tool.execute(arguments={"max_count": 1})
        assert not result.is_error
        assert "initial" in result.content


class TestGitToolsWithoutSandbox:
    """Git tools work without sandbox (backward compat)."""

    async def test_status_without_sandbox(self, tmp_path: Path) -> None:
        _init_repo(tmp_path)
        tool = GitStatusTool(workspace=tmp_path)
        result = await tool.execute(arguments={})
        assert not result.is_error

    async def test_log_without_sandbox(self, tmp_path: Path) -> None:
        _init_repo(tmp_path)
        tool = GitLogTool(workspace=tmp_path)
        result = await tool.execute(arguments={"max_count": 1})
        assert not result.is_error
        assert "initial" in result.content


class TestSandboxTimeoutSurfaces:
    """Sandbox timeout surfaces as ToolExecutionResult(is_error=True)."""

    async def test_sandbox_timeout_returns_error(
        self,
        tmp_path: Path,
    ) -> None:
        _init_repo(tmp_path)
        sandbox = SubprocessSandbox(workspace=tmp_path)
        # Mock execute to return a timed-out result
        sandbox.execute = AsyncMock(  # type: ignore[method-assign]
            return_value=SandboxResult(
                stdout="",
                stderr="Process timed out after 1s",
                returncode=-1,
                timed_out=True,
            ),
        )
        tool = GitStatusTool(workspace=tmp_path, sandbox=sandbox)
        result = await tool.execute(arguments={})
        assert result.is_error
        assert "timed out" in result.content.lower()


class TestSandboxErrorSurfaces:
    """SandboxError surfaces as ToolExecutionResult(is_error=True)."""

    async def test_sandbox_error_returns_error(
        self,
        tmp_path: Path,
    ) -> None:
        _init_repo(tmp_path)
        sandbox = SubprocessSandbox(workspace=tmp_path)
        sandbox.execute = AsyncMock(  # type: ignore[method-assign]
            side_effect=SandboxError("workspace violation"),
        )
        tool = GitStatusTool(workspace=tmp_path, sandbox=sandbox)
        result = await tool.execute(arguments={})
        assert result.is_error
        assert "workspace violation" in result.content


class TestGitHardeningWithSandbox:
    """Git hardening env vars are passed via env_overrides."""

    async def test_env_overrides_contain_hardening_vars(
        self,
        tmp_path: Path,
    ) -> None:
        _init_repo(tmp_path)
        sandbox = SubprocessSandbox(workspace=tmp_path)
        original_execute = sandbox.execute
        captured_overrides: dict[str, str] = {}

        async def capture_execute(**kwargs: object) -> SandboxResult:
            overrides = kwargs.get("env_overrides")
            if isinstance(overrides, dict):
                captured_overrides.update(overrides)
            return await original_execute(**kwargs)  # type: ignore[arg-type]

        sandbox.execute = capture_execute  # type: ignore[method-assign]
        tool = GitStatusTool(workspace=tmp_path, sandbox=sandbox)
        await tool.execute(arguments={})

        assert captured_overrides.get("GIT_TERMINAL_PROMPT") == "0"
        assert captured_overrides.get("GIT_CONFIG_NOSYSTEM") == "1"
        assert captured_overrides.get("GIT_PROTOCOL_FROM_USER") == "0"
